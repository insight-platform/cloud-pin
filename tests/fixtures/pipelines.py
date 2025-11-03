import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest_asyncio
from savant_rs.zmq import ReaderConfigBuilder, ReaderResultMessage, WriterConfigBuilder

from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.fixtures.connections import opposite_dir_url


@asynccontextmanager
async def run_identity_pipeline(
    server_sink_url: str, server_source_url: str
) -> AsyncGenerator:
    source_cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(server_sink_url)}")
    source = NonBlockingReader(source_cfg.build(), results_queue_size=100)
    sink_cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(server_source_url)}")
    sink = NonBlockingWriter(sink_cfg.build(), max_inflight_messages=100)

    async def pipeline() -> None:
        while running:
            if sink.has_capacity():
                while msg := source.try_receive():
                    if isinstance(msg, ReaderResultMessage):
                        sink.send_message(msg.topic, msg.message, msg.data(0))
            await asyncio.sleep(0.01)

    running = True
    with sink, source:
        sink.start()
        source.start()

        process_task = asyncio.create_task(pipeline())
        yield

        running = False
        await process_task


@pytest_asyncio.fixture
async def identity_pipeline(
    server_sink_url: str, server_source_url: str
) -> AsyncGenerator:
    async with run_identity_pipeline(server_sink_url, server_source_url):
        yield


@pytest_asyncio.fixture
async def var_identity_pipeline(
    var_sink_url: str, var_source_url: str
) -> AsyncGenerator:
    async with run_identity_pipeline(var_sink_url, var_source_url):
        yield
