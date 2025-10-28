import asyncio
import ssl
from asyncio import Event
from collections import deque
from functools import cached_property, partial
from ssl import SSLContext
from typing import NamedTuple, override
from urllib.parse import urlparse

from picows import WSFrame, WSListener, WSMsgType, WSTransport, ws_connect
from picows.picows import WSError
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.cfg import ClientServiceConfig
from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.services._base import ServiceBase
from savant_cloudpin.services._protocol import API_KEY_HEADER
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
        self._upstream_url = protocol.upstream_url(ws_url)
        self._downstream_url = protocol.downstream_url(ws_url)
        self._source = NonBlockingReader(
            *config.source.as_router().nonblocking_params()
        )
        self._sink = NonBlockingWriter(*config.sink.as_dealer().nonblocking_params())
        self._downstream_queue = deque[WSFrame]()
        self._upstream: ActiveConnection[UpstreamListener] | None = None
        self._downstream: ActiveConnection[DownstreamListener] | None = None

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.load_verify_locations(self._ssl.ca_file)
        ctx.check_hostname = self._ssl.check_hostname
        ctx.hostname_checks_common_name = self._ssl.check_hostname

        if self._ssl.cert_file and self._ssl.key_file:
            ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        return ctx

    async def _wait_active_upstream(self) -> WSTransport | None:
        if not self._upstream or self._upstream.listener.disconnected:
            try:
                transport, listener = await ws_connect(
                    ws_listener_factory=UpstreamListener,
                    url=self._upstream_url,
                    ssl_context=self._ssl_context,
                    extra_headers={API_KEY_HEADER: self._api_key},
                )
            except ConnectionRefusedError, ConnectionResetError:
                await asyncio.sleep(self._io_timeout)
                return None
            except ssl.SSLCertVerificationError as orig_err:
                raise ConnectionError(
                    "Error connecting upstream. Certificate verify failed"
                ) from orig_err
            except WSError as orig_err:
                err = ConnectionError("Error connecting upstream. Maybe auth problems")
                raise err from orig_err
            if not isinstance(listener, UpstreamListener):
                raise ConnectionError("Error connecting upstream. Maybe auth problems")
            self._upstream = ActiveConnection(transport, listener)

        transport, listener = self._upstream
        if not listener.disconnected:
            try:
                await asyncio.wait_for(listener.active.wait(), self._io_timeout)
                return transport
            except TimeoutError:
                pass
        return None

    async def _ensure_active_downstream(self) -> None:
        if self._downstream and not self._downstream.listener.disconnected:
            return
        try:
            transport, listener = await ws_connect(
                ws_listener_factory=partial(DownstreamListener, self._downstream_queue),
                url=self._downstream_url,
                ssl_context=self._ssl_context,
                extra_headers={API_KEY_HEADER: self._api_key},
            )
        except ConnectionRefusedError, ConnectionResetError:
            await asyncio.sleep(self._io_timeout)
            return
        except ssl.SSLCertVerificationError as orig_err:
            raise ConnectionError(
                "Error connecting downstream. Certificate verify failed"
            ) from orig_err
        except WSError as orig_err:
            err = ConnectionError("Error connecting downstream. Maybe auth problems")
            raise err from orig_err
        if not isinstance(listener, DownstreamListener):
            raise ConnectionError("Error connecting downstream. Maybe auth problems")
        self._downstream = ActiveConnection(transport, listener)

    async def _upstream_loop(self) -> None:
        while self.running:
            upstream = await self._wait_active_upstream()
            if not upstream or self._source.is_empty():
                await asyncio.sleep(self._io_timeout)
                continue

            msg = self._source.try_receive()
            if not isinstance(msg, ReaderResultMessage):
                await asyncio.sleep(self._io_timeout)
                continue

            packed = protocol.pack_stream_frame(msg.topic, msg.message, msg.data(0))
            upstream.send(WSMsgType.BINARY, packed)

    async def _downstream_loop(self) -> None:
        while self.running:
            while self._downstream_queue and self._sink.has_capacity():
                frame = self._downstream_queue.popleft()
                topic, msg, extra = protocol.unpack_stream_frame(frame)
                self._sink.send_message(topic, msg, extra)

            await self._ensure_active_downstream()
            await asyncio.sleep(self._io_timeout)

    async def _ensure_closed_websockets(self):
        if self._upstream:
            self._upstream.transport.send_close()
            await self._upstream.transport.wait_disconnected()
        if self._downstream:
            self._downstream.transport.send_close()
            await self._downstream.transport.wait_disconnected()

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


class ActiveConnection[T: WSListener](NamedTuple):
    transport: WSTransport
    listener: T


class UpstreamListener(WSListener):
    def __init__(self) -> None:
        self.disconnected = False
        self.active = Event()

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        self.disconnected = False
        self.active.set()

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.disconnected = True
        self.active.clear()

    @override
    def pause_writing(self) -> None:
        self.active.clear()

    @override
    def resume_writing(self) -> None:
        self.active.set()


class DownstreamListener(WSListener):
    def __init__(self, queue: deque[WSFrame]) -> None:
        self.disconnected = False
        self.queue = queue

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        self.disconnected = False

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.disconnected = True

    @override
    def on_ws_frame(self, transport: WSTransport, frame: WSFrame) -> None:
        if frame.msg_type == WSMsgType.BINARY:
            self.queue.append(frame)
