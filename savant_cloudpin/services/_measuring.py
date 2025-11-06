from asyncio import Queue
from collections.abc import Sequence
from functools import cache, cached_property
from typing import Any, Literal, TypedDict, cast

from opentelemetry.metrics import (
    Counter,
    Histogram,
    Instrument,
    Meter,
    MeterProvider,
    NoOpMeterProvider,
    get_meter_provider,
)
from opentelemetry.util.types import Attributes
from savant_rs.utils.serialization import Message

from savant_cloudpin.cfg import MetricsConfig
from savant_cloudpin.services._video_frame import (
    LABEL_CLIENT_SINK,
    LABEL_CLIENT_SOURCE,
    LABEL_SERVER_SINK,
    LABEL_SERVER_SOURCE,
    VideoFrameTimings,
)
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter

METER_NAME = "CloudPin"
JAEGER_TRACE_HEADER = "uber-trace-id"
W3C_TRACE_HEADER = "traceparent"
NOOP_METER_PROVIDER = NoOpMeterProvider()

type ContextPropagationFormat = Literal["Jaeger", "W3C"]
type ServiceSide = Literal["Server", "Client"]
type ZMQSocket = Literal["Source", "Sink"]


class MetricAttrs(TypedDict, total=False):
    service: ServiceSide
    socket: ZMQSocket
    propagation: Sequence[ContextPropagationFormat] | ContextPropagationFormat
    path_start: ServiceSide
    path_end: ServiceSide


class Metrics:
    _meter_provider: MeterProvider = NOOP_METER_PROVIDER

    def __init__(self, config: MetricsConfig) -> None:
        self._boundaries = config.histogram_boundaries

    @cached_property
    def _meter(self) -> Meter:
        return self._meter_provider.get_meter(METER_NAME)

    def _reset_cache(self) -> None:
        attrs = [
            attr
            for attr, val in self.__dict__.items()
            if isinstance(val, (Instrument, Meter))
        ]
        for attr in attrs:
            del self.__dict__[attr]

    def reset_meter_provider(self) -> None:
        self._meter_provider = get_meter_provider()
        self._reset_cache()

    @cached_property
    def traces(self) -> Counter:
        return self._meter.create_counter(
            name="traces", description="ZeroMQ message telemetry traces"
        )

    @cached_property
    def messages(self) -> Counter:
        return self._meter.create_counter(
            name="messages", description="ZeroMQ messages"
        )

    @cached_property
    def delay(self) -> Histogram:
        return self._meter.create_histogram(
            name="delay",
            description="Delay caused by message processing",
            explicit_bucket_boundaries_advisory=self._boundaries.delay or None,
        )

    @cached_property
    def left_zmq_capacity(self) -> Histogram:
        return self._meter.create_histogram(
            name="left_zmq_capacity",
            description="Left ZeroMQ socket capacity",
            explicit_bucket_boundaries_advisory=self._boundaries.left_zmq_capacity
            or None,
        )

    @cached_property
    def consumed_zmq_capacity(self) -> Histogram:
        return self._meter.create_histogram(
            name="consumed_zmq_capacity",
            description="Consumed ZeroMQ socket capacity",
            explicit_bucket_boundaries_advisory=self._boundaries.consumed_zmq_capacity
            or None,
        )

    @cached_property
    def left_ws_reading_capacity(self) -> Histogram:
        return self._meter.create_histogram(
            name="left_ws_reading_capacity",
            description="Left WebSockets reading queue capacity",
            explicit_bucket_boundaries_advisory=self._boundaries.left_ws_reading_capacity
            or None,
        )

    @cached_property
    def consumed_ws_reading_capacity(self) -> Histogram:
        return self._meter.create_histogram(
            name="left_ws_reading_capacity",
            description="Consumed WebSockets reading queue capacity",
            explicit_bucket_boundaries_advisory=self._boundaries.consumed_ws_reading_capacity
            or None,
        )

    @cached_property
    def message_size(self) -> Histogram:
        return self._meter.create_histogram(
            name="message_size",
            description="Data size of WebSockets message",
            explicit_bucket_boundaries_advisory=self._boundaries.message_size or None,
        )

    @cached_property
    def ws_writing_pauses(self) -> Counter:
        return self._meter.create_counter(
            name="ws_writing_pauses", description="WebSockets writing pauses"
        )

    @cached_property
    def ws_writing_resumed(self) -> Counter:
        return self._meter.create_counter(
            name="ws_writing_resumed", description="Resumed WebSockets writing"
        )

    @cached_property
    def ws_connection_attempts(self) -> Counter:
        return self._meter.create_counter(
            name="ws_connection_attempts",
            description="Attempts to establish WebSockets connection",
        )

    @cached_property
    def ws_connection_errors(self) -> Counter:
        return self._meter.create_counter(
            name="ws_connection_errors",
            description="Errors establishing WebSockets connection",
        )

    @cached_property
    def ws_read_drops(self) -> Counter:
        return self._meter.create_counter(
            name="ws_read_drops", description="Read WebSockets messages dropped"
        )

    @cached_property
    def ws_connected(self) -> Counter:
        return self._meter.create_counter(
            name="ws_connected", description="Established WebSockets connection"
        )

    @cached_property
    def ws_disconnected(self) -> Counter:
        return self._meter.create_counter(
            name="ws_disconnected", description="Disconnected WebSockets connection"
        )


class Measurements:
    def __init__(self, service: ServiceSide, config: MetricsConfig | None) -> None:
        self._service = service
        self.metrics = Metrics(config or MetricsConfig())

    @cache
    def _attrs(
        self,
        *,
        socket: ZMQSocket | None = None,
        w3c_propagation: bool = False,
        jaeger_propagation: bool = False,
        path_start: ServiceSide | None = None,
        path_end: ServiceSide | None = None,
    ) -> Attributes:
        attrs = MetricAttrs(service=self._service)
        if socket:
            attrs.update(socket=socket)
        if path_start:
            attrs.update(path_start=path_start)
        if path_end:
            attrs.update(path_end=path_end)
        match w3c_propagation, jaeger_propagation:
            case True, False:
                attrs.update(propagation="W3C")
            case False, True:
                attrs.update(propagation="Jaeger")
            case True, True:
                attrs.update(propagation=("Jaeger", "W3C"))
            case _:
                pass
        return cast(Attributes, attrs)

    def measure_sink_message(self, message: Message) -> Message:
        return self._measure_message(message, socket="Sink")

    def measure_source_message(self, message: Message) -> Message:
        return self._measure_message(message, socket="Source")

    def _measure_message(self, message: Message, socket: ZMQSocket) -> Message:
        self.metrics.messages.add(1, self._attrs(socket=socket))
        self._count_trace(message, socket)
        return self._measure_video_frame(message, socket)

    def _count_trace(self, message: Message, socket: ZMQSocket) -> None:
        span = getattr(message, "span_context", None)
        context: dict[str, Any] | None = span.as_dict() if span else None
        if not context:
            return

        attrs = self._attrs(
            socket=socket,
            w3c_propagation=W3C_TRACE_HEADER in context,
            jaeger_propagation=JAEGER_TRACE_HEADER in context,
        )
        self.metrics.traces.add(1, attributes=attrs)

    def _measure_video_frame(self, message: Message, socket: ZMQSocket) -> Message:
        timings = VideoFrameTimings(message)
        match self._service, socket:
            case "Client", "Source":
                timings.append_timing(LABEL_CLIENT_SOURCE, truncate=True)
            case "Server", "Sink":
                timings.append_timing(LABEL_SERVER_SINK)
            case "Server", "Source":
                timings.append_timing(LABEL_SERVER_SOURCE)
            case "Client", "Sink":
                timings.append_timing(LABEL_CLIENT_SINK)

        self._detect_video_frame_delay(timings)
        return timings.message

    def _detect_video_frame_delay(self, timings: VideoFrameTimings) -> None:
        delay = timings.get_delay(LABEL_CLIENT_SOURCE, LABEL_SERVER_SINK)
        if delay is not None:
            self.metrics.delay.record(
                delay, self._attrs(path_start="Client", path_end="Server")
            )
        delay = timings.get_delay(LABEL_SERVER_SINK, LABEL_SERVER_SOURCE)
        if delay is not None:
            self.metrics.delay.record(
                delay, self._attrs(path_start="Server", path_end="Server")
            )
        delay = timings.get_delay(LABEL_SERVER_SOURCE, LABEL_CLIENT_SINK)
        if delay is not None:
            self.metrics.delay.record(
                delay, self._attrs(path_start="Server", path_end="Client")
            )
        delay = timings.get_delay(LABEL_CLIENT_SOURCE, LABEL_CLIENT_SINK)
        if delay is not None:
            self.metrics.delay.record(
                delay, self._attrs(path_start="Client", path_end="Client")
            )

    def measure_zmq_capacity(
        self, socket: NonBlockingReader | NonBlockingWriter
    ) -> None:
        match socket:
            case NonBlockingReader():
                attrs = self._attrs(socket="Source")
                consumed = socket.enqueued_results()
                total = socket.results_queue_size
            case NonBlockingWriter():
                attrs = self._attrs(socket="Sink")
                consumed = socket.inflight_messages()
                total = socket.max_inflight_messages
            case _:
                return

        self.metrics.consumed_zmq_capacity.record(consumed, attrs)
        self.metrics.left_zmq_capacity.record(total - consumed, attrs)

    def measure_ws_reading_capacity(self, queue: Queue) -> None:
        attrs = self._attrs(socket="Sink")
        consumed = queue.qsize()
        total = queue.maxsize

        self.metrics.consumed_ws_reading_capacity.record(consumed, attrs)
        self.metrics.left_ws_reading_capacity.record(total - consumed, attrs)

    def measure_source_message_data(self, frame: bytes) -> None:
        self._measure_message_data(frame, "Source")

    def measure_sink_message_data(self, frame: bytes) -> None:
        self._measure_message_data(frame, "Sink")

    def _measure_message_data(self, frame: bytes, socket: ZMQSocket) -> None:
        self.metrics.message_size.record(len(frame), self._attrs(socket=socket))

    def increment_ws_writing_pauses(self) -> None:
        self.metrics.ws_writing_pauses.add(1, self._attrs())

    def increment_ws_writing_resumed(self) -> None:
        self.metrics.ws_writing_resumed.add(1, self._attrs())

    def increment_ws_connection_attempts(self) -> None:
        self.metrics.ws_connection_attempts.add(1, self._attrs())

    def increment_ws_connection_errors(self) -> None:
        self.metrics.ws_connection_errors.add(1, self._attrs())

    def increment_ws_read_drops(self) -> None:
        self.metrics.ws_read_drops.add(1, self._attrs(socket="Sink"))

    def increment_ws_connected(self) -> None:
        self.metrics.ws_connected.add(1, self._attrs())

    def increment_ws_disconnected(self) -> None:
        self.metrics.ws_disconnected.add(1, self._attrs())
