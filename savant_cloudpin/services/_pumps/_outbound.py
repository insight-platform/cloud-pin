from typing import NamedTuple, override

from picows import WSCloseCode, WSListener, WSMsgType, WSTransport
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.zmq import NonBlockingReader


class ActiveConnection(NamedTuple):
    transport: WSTransport
    listener: OutboundWSListener


class OutboundWSPump:
    def __init__(self, source: NonBlockingReader) -> None:
        self.source = source
        self.connection: ActiveConnection | None = None

    def create_listener(self) -> OutboundWSListener:
        return OutboundWSListener(self)

    def is_connected(self) -> bool:
        return self.connection is not None and not self.connection.listener.disconnected

    def active_connection(self) -> WSTransport | None:
        if self.connection and self.connection.listener.active:
            return self.connection.transport
        return None

    def pump_one(self) -> bool:
        transport = self.active_connection()
        if not transport or self.source.is_empty():
            return False

        while msg := self.source.try_receive():
            if isinstance(msg, ReaderResultMessage):
                break
        else:
            return False

        packed = protocol.pack_stream_frame(msg.topic, msg.message, msg.data(0))
        transport.send(WSMsgType.BINARY, packed)
        return True


class OutboundWSListener(WSListener):
    def __init__(self, pump: OutboundWSPump) -> None:
        self.active = False
        self.pump = pump
        self.disconnected = False

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        self.disconnected = False
        existing = self.pump.connection
        if existing and not existing.listener.disconnected:
            transport.send_close(WSCloseCode.POLICY_VIOLATION)
        else:
            self.disconnected = False
            self.pump.connection = ActiveConnection(transport, self)
            self.active = True

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.disconnected = True
        self.active = False

    @override
    def pause_writing(self) -> None:
        self.active = False

    @override
    def resume_writing(self) -> None:
        self.active = True
