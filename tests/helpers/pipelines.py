import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from savant_rs import telemetry
from savant_rs.telemetry import (
    ContextPropagationFormat,
    Protocol,
    TelemetryConfiguration,
    TracerConfiguration,
)
from savant_rs.utils import TelemetrySpan
from savant_rs.zmq import ReaderConfigBuilder, ReaderResultMessage, WriterConfigBuilder

from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.messages import MessageData


@asynccontextmanager
async def run_identity_pipeline(
    zmq_src_endpoint: str, zmq_sink_endpoint: str, io_timeout: float = 0.01
) -> AsyncGenerator:
    src_cfg = ReaderConfigBuilder(f"router+{zmq_src_endpoint}")
    src = NonBlockingReader(src_cfg.build(), results_queue_size=100)
    sink_cfg = WriterConfigBuilder(f"dealer+{zmq_sink_endpoint}")
    sink = NonBlockingWriter(sink_cfg.build(), max_inflight_messages=100)

    async def pipeline() -> None:
        while running:
            if sink.has_capacity():
                while msg := src.try_receive():
                    if isinstance(msg, ReaderResultMessage):
                        sink.send_message(msg.topic, msg.message, msg.data(0))
            await asyncio.sleep(io_timeout)

    running = True
    with sink, src:
        sink.start()
        src.start()

        process_task = asyncio.create_task(pipeline())
        yield

        running = False
        await process_task


def init_telemetry_tracer(
    endpoint: str,
    name: str = "test_tracer",
    trace_format: (
        ContextPropagationFormat | int | None
    ) = ContextPropagationFormat.Jaeger,
) -> None:
    cfg = TelemetryConfiguration(
        tracer=TracerConfiguration(
            service_name=name,
            endpoint=endpoint,
            protocol=Protocol.HttpJson,  # type: ignore
        ),
        context_propagation_format=trace_format,  # type: ignore
    )
    telemetry.init(cfg)


@asynccontextmanager
async def run_infinite_write(
    zmq_sink_endpoint: str, io_timeout: float = 0.01
) -> AsyncGenerator:
    sink_cfg = WriterConfigBuilder(f"dealer+{zmq_sink_endpoint}")
    sink = NonBlockingWriter(sink_cfg.build(), max_inflight_messages=100)

    async def pipeline() -> None:
        while running:
            await asyncio.sleep(io_timeout)
            if not sink.has_capacity():
                continue
            with TelemetrySpan("sink") as span:
                topic, message, extra = MessageData.fake()
                message.span_context = span.propagate()  # type: ignore
                sink.send_message(topic, message, extra)
                span.set_status_ok()

    running = True
    with sink:
        sink.start()
        process_task = asyncio.create_task(pipeline())

        yield
        running = False
        await process_task


@asynccontextmanager
async def run_infinite_read(
    zmq_src_endpoint: str, io_timeout: float = 0.01
) -> AsyncGenerator:
    src_cfg = ReaderConfigBuilder(f"router+{zmq_src_endpoint}")
    src = NonBlockingReader(src_cfg.build(), results_queue_size=100)

    async def pipeline() -> None:
        while running:
            await asyncio.sleep(io_timeout)
            while not src.is_empty():
                with TelemetrySpan("source") as span:
                    src.try_receive()
                    span.set_status_ok()

    running = True
    with src:
        src.start()
        process_task = asyncio.create_task(pipeline())

        yield
        running = False
        await process_task
