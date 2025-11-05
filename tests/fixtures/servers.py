import copy
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from savant_cloudpin.cfg import (
    ClientServiceConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    WriterConfig,
)
from savant_cloudpin.services import ServerService, create_service
from tests.helpers.ssl import SignedCertKey


@pytest.fixture
def server_ws_config(
    ws_url: str, api_key: str, server_ssl_config: ServerSSLConfig
) -> ServerWSConfig:
    return ServerWSConfig(
        server_url=ws_url,
        api_key=api_key,
        ssl=ServerSSLConfig(
            ca_file=server_ssl_config.ca_file,
            cert_file=server_ssl_config.cert_file,
            key_file=server_ssl_config.key_file,
            client_cert_required=True,
        ),
    )


@pytest.fixture
def server_config(
    server_source_config: ReaderConfig,
    server_sink_config: WriterConfig,
    server_ws_config: ServerWSConfig,
) -> ServerServiceConfig:
    return ServerServiceConfig(
        io_timeout=0.01,
        websockets=server_ws_config,
        source=server_source_config,
        sink=server_sink_config,
    )


@pytest.fixture
def var_server_config(
    var_source_config: ReaderConfig,
    var_sink_config: WriterConfig,
    server_ws_config: ServerWSConfig,
) -> ServerServiceConfig:
    return ServerServiceConfig(
        io_timeout=0.01,
        websockets=server_ws_config,
        source=var_source_config,
        sink=var_sink_config,
    )


@pytest_asyncio.fixture
async def server(server_config: ServerServiceConfig) -> AsyncGenerator[ServerService]:
    async with create_service(server_config) as service:
        yield service


@pytest_asyncio.fixture
async def var_server(
    var_server_config: ServerServiceConfig,
) -> AsyncGenerator[ServerService]:
    async with create_service(var_server_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_cert_server(
    server_config: ServerServiceConfig, another_cert: SignedCertKey
) -> AsyncGenerator[ServerService]:
    another_cert_config = copy.deepcopy(server_config)
    ssl = another_cert_config.websockets.ssl
    assert ssl is not None
    ssl.cert_file = another_cert.cert_file
    ssl.key_file = another_cert.key_file
    async with create_service(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def same_cert_server(
    server_config: ServerServiceConfig,
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ServerService]:
    another_cert_config = copy.deepcopy(server_config)
    ssl = another_cert_config.websockets.ssl
    client_ssl = client_config.websockets.ssl

    assert ssl is not None and client_ssl.cert_file and client_ssl.key_file
    ssl.cert_file = client_ssl.cert_file
    ssl.key_file = client_ssl.key_file

    async with create_service(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def nossl_server(
    server_config: ServerServiceConfig,
) -> AsyncGenerator[ServerService]:
    nossl_config = copy.deepcopy(server_config)
    nossl_config.websockets.ssl = None
    async with create_service(nossl_config) as service:
        yield service
