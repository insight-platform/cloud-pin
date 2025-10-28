import asyncio
import ssl
from asyncio.base_events import Server
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import cached_property
from ssl import SSLContext
from typing import override
from urllib.parse import urlparse

from picows import WSListener, WSUpgradeRequest, ws_create_server

from savant_cloudpin.cfg import ServerServiceConfig
from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.services._base import ServiceBase
from savant_cloudpin.services._protocol import API_KEY_HEADER
from savant_cloudpin.services._pumps import InboundWSPump, OutboundWSPump
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter


class ServerService(ServiceBase["ServerService"]):
    def __init__(self, config: ServerServiceConfig) -> None:
        super().__init__()
        default_port = "443" if config.websockets.ssl else "80"
        ws_url = config.websockets.server_url
        netloc = urlparse(ws_url).netloc.split(":")

        self._host = netloc.pop(0)
        self._port = int(netloc.pop() if netloc else default_port)
        self._io_timeout = config.io_timeout
        self._ssl = config.websockets.ssl
        self._api_key = config.websockets.api_key

        self._sink = NonBlockingWriter(*config.sink.as_dealer().to_args())
        self._source = NonBlockingReader(*config.source.as_router().to_args())

        self._upstream_path = urlparse(protocol.upstream_url(ws_url)).path.encode()
        self._downstream_path = urlparse(protocol.downstream_url(ws_url)).path.encode()
        self._upstream = InboundWSPump(
            sink=self._sink, queue_limit=2 * config.sink.max_inflight_messages
        )
        self._downstream = OutboundWSPump(source=self._source)

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        if not self._ssl:
            return None

        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        if self._ssl.client_cert_required:
            ctx.verify_mode = ssl.VerifyMode.CERT_REQUIRED
            ctx.load_verify_locations(cafile=self._ssl.ca_file)
        return ctx

    def _create_listener(self, request: WSUpgradeRequest) -> WSListener:
        client_api_key = request.headers.get(API_KEY_HEADER, None)
        if self._api_key != client_api_key:
            raise ConnectionRefusedError("Invalid API key")
        match request.path:
            case self._upstream_path:
                return self._upstream.create_listener()
            case self._downstream_path:
                return self._downstream.create_listener()
            case _:
                raise ConnectionRefusedError("Invalid URL path")

    @asynccontextmanager
    async def _create_server(self) -> AsyncGenerator[Server]:
        server = await ws_create_server(
            ws_listener_factory=self._create_listener,
            host=self._host,
            port=self._port,
            ssl=self._ssl_context,
        )
        async with server:
            yield server
            server.close_clients()

    async def _upstream_loop(self) -> None:
        while self.running:
            pumped = self._downstream.pump_one()
            await asyncio.sleep(0 if pumped else self._io_timeout)

    async def _downstream_loop(self) -> None:
        while self.running:
            self._upstream.pump_many()
            await asyncio.sleep(self._io_timeout)

    @override
    async def _serve(self) -> None:
        with self._source, self._sink:
            async with self._create_server() as server:
                self._source.start()
                self._sink.start()

                await server.start_serving()

                self.started.set()
                await asyncio.gather(
                    self._upstream_loop(),
                    self._downstream_loop(),
                )
