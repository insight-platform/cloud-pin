import asyncio
import ssl
from asyncio import Event
from collections import deque
from functools import cached_property
from ssl import SSLContext
from typing import NamedTuple, override
from urllib.parse import urlparse

from picows import WSFrame, WSListener, WSMsgType, WSTransport, ws_create_server
from picows.picows import WSUpgradeRequest

from savant_cloudpin.cfg import ServerServiceConfig
from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.services._base import ServiceBase
from savant_cloudpin.services._protocol import API_KEY_HEADER


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
        self._upstream_path = urlparse(protocol.upstream_url(ws_url)).path.encode()
        self._downstream_path = urlparse(protocol.downstream_url(ws_url)).path.encode()
        self._upstream_queue = deque[bytes]()
        self._downstreams = list[ActiveConnection]()

    def _listener_factory(self, request: WSUpgradeRequest) -> WSListener:
        client_api_key = request.headers.get(API_KEY_HEADER, None)
        if self._api_key != client_api_key:
            raise ConnectionRefusedError("Invalid API key")
        match request.path:
            case self._upstream_path:
                return UpstreamListener(self._upstream_queue)
            case self._downstream_path:
                return DownstreamListener(self._downstreams)
            case _:
                raise ConnectionRefusedError("Invalid URL path")

    async def _wait_active_downstream(self) -> WSTransport | None:
        for transport, active in self._downstreams:
            try:
                await asyncio.wait_for(active.wait(), self._io_timeout)
                return transport
            except TimeoutError:
                continue
        return None

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

    async def _loop(self) -> None:
        while self.running:
            downstream = await self._wait_active_downstream()
            if downstream and self._upstream_queue:
                frame = self._upstream_queue.popleft()
                downstream.send(WSMsgType.BINARY, frame)
            else:
                await asyncio.sleep(self._io_timeout)

    @override
    async def _serve(self) -> None:
        server = None
        try:
            server = await ws_create_server(
                ws_listener_factory=self._listener_factory,
                host=self._host,
                port=self._port,
                ssl=self._ssl_context,
            )
            await server.start_serving()
            self.started.set()

            await self._loop()
        finally:
            if not server:
                return
            server.close_clients()
            server.close()
            await server.wait_closed()


class ActiveConnection(NamedTuple):
    transport: WSTransport
    active: Event


class UpstreamListener(WSListener):
    def __init__(self, queue: deque[bytes]) -> None:
        self.queue = queue

    @override
    def on_ws_frame(self, transport: WSTransport, frame: WSFrame) -> None:
        if frame.msg_type != WSMsgType.BINARY:
            return
        self.queue.append(frame.get_payload_as_bytes())


class DownstreamListener(WSListener):
    def __init__(self, downsteams: list[ActiveConnection]) -> None:
        self.active = Event()
        self.downsteams = downsteams

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        self.downsteams.append(ActiveConnection(transport, self.active))
        self.active.set()

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.active.clear()
        self.downsteams.remove(ActiveConnection(transport, self.active))

    @override
    def pause_writing(self) -> None:
        self.active.clear()

    @override
    def resume_writing(self) -> None:
        self.active.set()
