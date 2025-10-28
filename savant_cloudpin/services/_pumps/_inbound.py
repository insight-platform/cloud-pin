from collections import deque
from typing import NamedTuple, override

from picows import WSCloseCode, WSFrame, WSListener, WSMsgType, WSTransport

from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.zmq import NonBlockingWriter


class ActiveConnection(NamedTuple):
    transport: WSTransport
    listener: InboundWSListener


class InboundWSPump:
    def __init__(self, sink: NonBlockingWriter, queue_limit: int) -> None:
        self.sink = sink
        self.queue = deque[bytes]()
        self.queue_limit = queue_limit
        self.connection: ActiveConnection | None = None

    def create_listener(self) -> InboundWSListener:
        return InboundWSListener(self)

    def is_connected(self) -> bool:
        return self.connection is not None and not self.connection.listener.disconnected

    def pump_many(self) -> None:
        if self.connection:
            self.connection.listener.flush_queue()
            self.connection.listener.throttle_ws_pressure()


class InboundWSListener(WSListener):
    def __init__(self, pump: InboundWSPump) -> None:
        self.pump = pump
        self.sink = pump.sink
        self.queue = pump.queue
        self.queue_limit = pump.queue_limit
        self.disconnected = False

    def throttle_ws_pressure(self) -> None:
        connection = self.pump.connection
        if connection and self.queue and not self.sink.has_capacity():
            connection.transport.send_close(WSCloseCode.TRY_AGAIN_LATER)

    def flush_queue(self) -> None:
        while self.queue and self.sink.has_capacity():
            frame = self.queue.popleft()
            topic, msg, extra = protocol.unpack_stream_frame(frame)
            self.sink.send_message(topic, msg, extra)

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        existing = self.pump.connection
        if existing and not existing.listener.disconnected:
            transport.send_close(WSCloseCode.POLICY_VIOLATION)
        elif not self.sink.has_capacity():
            transport.send_close(WSCloseCode.TRY_AGAIN_LATER)
        else:
            self.disconnected = False
            self.pump.connection = ActiveConnection(transport, self)

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.disconnected = True

    @override
    def on_ws_frame(self, transport: WSTransport, frame: WSFrame) -> None:
        if frame.msg_type != WSMsgType.BINARY:
            return

        if len(self.queue) < self.queue_limit:
            self.queue.append(frame.get_payload_as_bytes())
