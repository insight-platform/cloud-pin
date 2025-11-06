from collections.abc import AsyncGenerator

import pytest_asyncio

from tests.helpers.connections import opposite_dir_url
from tests.helpers.pipelines import run_identity_pipeline


@pytest_asyncio.fixture
async def identity_pipeline(
    server_sink_url: str, server_source_url: str
) -> AsyncGenerator:
    async with run_identity_pipeline(
        source_url=opposite_dir_url(server_sink_url),
        sink_url=opposite_dir_url(server_source_url),
    ):
        yield


@pytest_asyncio.fixture
async def var_identity_pipeline(
    var_sink_url: str, var_source_url: str
) -> AsyncGenerator:
    async with run_identity_pipeline(
        source_url=opposite_dir_url(var_sink_url),
        sink_url=opposite_dir_url(var_source_url),
    ):
        yield
