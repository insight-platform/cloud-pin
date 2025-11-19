import asyncio
from abc import abstractmethod
from asyncio import Event, Queue
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import override

from picows import WSCloseCode, WSFrame, WSListener, WSMsgType, WSTransport
from savant_rs.py.log import get_logger
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.cfg._models import BaseServiceConfig
from savant_cloudpin.services import _protocol as protocol
from savant_cloudpin.services._measuring import Measurements
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter

_REPORT_INTERVAL = timedelta(seconds=1)

logger = get_logger(__package__ or __name__)


class LifeCycleServiceBase[T](AbstractAsyncContextManager[T]):
    def __init__(self, measurements: Measurements) -> None:
        self._measurements = measurements
        self.running = False
        self.started = Event()
        self.stopped = Event()
        self.stopped.set()

    @abstractmethod
    async def _serve(self) -> None: ...

    async def run(self) -> None:
        self._measurements.metrics.reset_meter_provider()
        logger.info("Running service ...")
        self.stopped.clear()
        self.running = True
        try:
            await self._serve()
        except:
            logger.exception("Service error")
            raise
        finally:
            self.stop_running()
            self.started.clear()
            self.stopped.set()
            logger.info("Service stopped")

    def stop_running(self) -> None:
        self.running = False

    async def stop(self) -> None:
        self.stop_running()
        await self.stopped.wait()

    @override
    async def __aexit__(self, *args) -> bool | None:
        await self.stop()
        return None


class PumpServiceBase[T](LifeCycleServiceBase[T]):
    def __init__(self, config: BaseServiceConfig, measurements: Measurements) -> None:
        super().__init__(measurements)
        self._io_timeout = config.io_timeout
        self._zmq_sink = NonBlockingWriter(*config.zmq_sink.as_dealer().to_args())
        self._zmq_src = NonBlockingReader(*config.zmq_src.as_router().to_args())
        self._sink_queue = Queue[bytes](
            maxsize=2 * config.zmq_sink.max_inflight_messages
        )
        self._sink_drops = 0
        self._last_log = datetime.now()
        self._connection: ServiceConnection | None = None

    def _create_listener(self) -> WSListener:
        return ServiceConnection(self)

    def _is_connected(self) -> bool:
        return bool(self._connection and self._connection.transport)

    def _writing_transport(self) -> WSTransport | None:
        if self._connection and self._connection.active_writing:
            return self._connection.transport
        return None

    def _log_dropped(self) -> None:
        if not self._sink_drops:
            return
        if datetime.now() - self._last_log < _REPORT_INTERVAL:
            return

        logger.warning(
            f"WebSockets sink queue limit exceeded. Dropped messages: {self._sink_drops}"
        )
        self._sink_drops = 0
        self._last_log = datetime.now()

    async def _inbound_ws_loop(self) -> None:
        while self.running:
            self._measurements.measure_zmq_capacity(self._zmq_sink)
            while self._zmq_sink.has_capacity():
                if self._sink_queue.empty():
                    get_task = asyncio.create_task(self._sink_queue.get())
                    logger.debug("Waiting inbound WebSockets ...")
                    while not get_task.done():
                        await asyncio.wait([get_task], timeout=self._io_timeout)
                        self._log_dropped()
                        self._measurements.measure_zmq_capacity(self._zmq_sink)
                        if not self.running:
                            return
                    frame = await get_task
                else:
                    frame = self._sink_queue.get_nowait()

                self._measurements.measure_sink_message_data(frame)
                topic, msg, extra = protocol.unpack_stream_frame(frame)
                self._measurements.add_sink_message_measure(msg)
                self._zmq_sink.send_message(topic, msg, extra)
                self._sink_queue.task_done()
                await asyncio.sleep(0)

            logger.debug(f"ZeroMQ sink queue is full. Waiting {self._io_timeout} sec.")
            await asyncio.sleep(self._io_timeout)
            self._log_dropped()

    async def _outbound_ws_loop(self) -> None:
        while self.running:
            self._measurements.measure_zmq_capacity(self._zmq_src)
            transport = self._writing_transport()
            if not transport or self._zmq_src.is_empty():
                if self._is_connected():
                    logger.debug(
                        f"WebSockets writing is paused. Waiting {self._io_timeout} sec."
                    )
                await asyncio.sleep(self._io_timeout)
                continue

            while msg := self._zmq_src.try_receive():
                if isinstance(msg, ReaderResultMessage):
                    break
            else:
                logger.debug(f"ZeroMQ source is empty. Waiting {self._io_timeout} sec.")
                await asyncio.sleep(self._io_timeout)
                continue

            topic, message, extra = msg.topic, msg.message, msg.data(0)
            self._measurements.add_src_message_measure(message)
            packed = protocol.pack_stream_frame(topic, message, extra)
            transport.send(WSMsgType.BINARY, packed)
            self._measurements.measure_src_message_data(packed)
            await asyncio.sleep(0)


class ServiceConnection(WSListener):
    transport: WSTransport | None = None

    def __init__(self, service: PumpServiceBase) -> None:
        self.service = service
        self.measurements = service._measurements
        self.sink_queue = service._sink_queue
        self.active_writing = False

    def current_transport(self) -> WSTransport | None:
        if not self.service._connection:
            return None
        return self.service._connection.transport

    def set_as_current(self) -> None:
        self.service._connection = self

    def increment_drops(self) -> None:
        self.measurements.increment_ws_read_drops()
        self.service._sink_drops += 1

    def shutdown(self) -> None:
        if self.transport:
            self.transport.send_close(WSCloseCode.GOING_AWAY)

    @override
    def on_ws_connected(self, transport: WSTransport) -> None:
        self.measurements.increment_ws_connected()
        logger.info("WebSockets connection established")
        existing = self.current_transport()
        if existing and transport != existing:
            transport.send_close(WSCloseCode.POLICY_VIOLATION)
            logger.warning("Unexpected extra Websockets connection. Disconnecting...")
        else:
            self.transport = transport
            self.active_writing = True
            self.set_as_current()

    @override
    def on_ws_disconnected(self, transport: WSTransport) -> None:
        self.measurements.increment_ws_disconnected()
        logger.info("WebSockets connection stopped")
        self.transport = None
        self.active_writing = False

    @override
    def on_ws_frame(self, transport: WSTransport, frame: WSFrame) -> None:
        if frame.msg_type != WSMsgType.BINARY:
            return

        self.measurements.measure_ws_reading_capacity(self.sink_queue)
        if not self.sink_queue.full():
            self.sink_queue.put_nowait(frame.get_payload_as_bytes())
        else:
            self.increment_drops()

    @override
    def pause_writing(self) -> None:
        self.active_writing = False
        self.measurements.increment_ws_writing_pauses()
        logger.warning("Pause WebSockets writing")

    @override
    def resume_writing(self) -> None:
        self.active_writing = True
        self.measurements.increment_ws_writing_resumed()
        logger.info("Resume WebSockets writing")
