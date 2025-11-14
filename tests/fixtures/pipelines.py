from collections.abc import AsyncGenerator

import pytest_asyncio

from tests.helpers.connections import opposite_dir_url
from tests.helpers.pipelines import run_identity_pipeline


@pytest_asyncio.fixture
async def identity_pipeline(
    server_zmq_sink_endpoint: str, server_zmq_src_endpoint: str
) -> AsyncGenerator:
    async with run_identity_pipeline(
        zmq_src_endpoint=opposite_dir_url(server_zmq_sink_endpoint),
        zmq_sink_endpoint=opposite_dir_url(server_zmq_src_endpoint),
    ):
        yield


@pytest_asyncio.fixture
async def var_identity_pipeline(
    var_zmq_sink_endpoint: str, var_zmq_src_endpoint: str
) -> AsyncGenerator:
    async with run_identity_pipeline(
        zmq_src_endpoint=opposite_dir_url(var_zmq_sink_endpoint),
        zmq_sink_endpoint=opposite_dir_url(var_zmq_src_endpoint),
    ):
        yield
