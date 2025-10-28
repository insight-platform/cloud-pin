import asyncio
import ssl
from collections.abc import Callable
from functools import cached_property
from ssl import SSLContext
from typing import override
from urllib.parse import urlparse

from picows import WSError, WSListener, WSTransport, ws_connect

from savant_cloudpin.cfg import ClientServiceConfig
from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.services._base import ServiceBase
from savant_cloudpin.services._protocol import API_KEY_HEADER
from savant_cloudpin.services._pumps import InboundWSPump, OutboundWSPump
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter


class ClientService(ServiceBase["ClientService"]):
    def __init__(self, config: ClientServiceConfig) -> None:
        super().__init__()
        ws_url = config.websockets.server_url
        scheme = urlparse(ws_url).scheme
        if scheme != "wss":
            raise ValueError(
                f"Invalid WebSocket URL scheme '{scheme}'. 'wss' is expected"
            )

        self._io_timeout = config.io_timeout
        self._ssl = config.websockets.ssl
        self._api_key = config.websockets.api_key

        self._source = NonBlockingReader(*config.source.as_router().to_args())
        self._sink = NonBlockingWriter(*config.sink.as_dealer().to_args())

        self._upstream_url = protocol.upstream_url(ws_url)
        self._downstream_url = protocol.downstream_url(ws_url)
        self._upstream = OutboundWSPump(source=self._source)
        self._downstream = InboundWSPump(
            sink=self._sink, queue_limit=2 * config.sink.max_inflight_messages
        )

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.load_verify_locations(self._ssl.ca_file)
        ctx.check_hostname = self._ssl.check_hostname
        ctx.hostname_checks_common_name = self._ssl.check_hostname

        if self._ssl.cert_file and self._ssl.key_file:
            ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        return ctx

    async def _connect(
        self, url: str, listener_factory: Callable[[], WSListener]
    ) -> None:
        listener = None
        try:
            _, listener = await ws_connect(
                ws_listener_factory=listener_factory,
                url=url,
                ssl_context=self._ssl_context,
                extra_headers={API_KEY_HEADER: self._api_key},
            )
        except ConnectionRefusedError, ConnectionResetError:
            await asyncio.sleep(self._io_timeout)
            return
        except ssl.SSLCertVerificationError as orig_err:
            err = ConnectionError("Error connecting {url}. Certificate plroblems")
            raise err from orig_err
        except WSError as orig_err:
            err = ConnectionError(f"Error connecting {url}. Maybe auth problems")
            raise err from orig_err
        if not listener:
            raise ConnectionError(f"Error connecting {url}. Maybe auth problems")

    async def _ensure_closed_websockets(self):
        errors = list[Exception]()
        transports = list[WSTransport]()

        if self._upstream.connection:
            transports.append(self._upstream.connection.transport)
        if self._downstream.connection:
            transports.append(self._downstream.connection.transport)

        for transport in transports:
            try:
                transport.send_close()
            except Exception as err:
                errors.append(err)

        if errors:
            raise ExceptionGroup("Error closing client transport", errors)

    async def _upstream_loop(self) -> None:
        while self.running:
            if not self._upstream.is_connected():
                await self._connect(self._upstream_url, self._upstream.create_listener)

            pumped = self._upstream.pump_one()
            await asyncio.sleep(0 if pumped else self._io_timeout)

    async def _downstream_loop(self) -> None:
        while self.running:
            if not self._downstream.is_connected():
                await self._connect(
                    self._downstream_url, self._downstream.create_listener
                )

            self._downstream.pump_many()
            await asyncio.sleep(self._io_timeout)

    @override
    async def _serve(self) -> None:
        try:
            with self._source, self._sink:
                self._source.start()
                self._sink.start()

                self.started.set()
                await asyncio.gather(
                    self._upstream_loop(),
                    self._downstream_loop(),
                )
        finally:
            await self._ensure_closed_websockets()
