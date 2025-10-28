import asyncio
import copy
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from faker import Faker

from savant_cloudpin.cfg import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    ReaderConfig,
    WriterConfig,
)
from savant_cloudpin.services import ClientService
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.ssl import SignedCertKey

fake = Faker()


@pytest.fixture
def client_ws_config(
    ws_url: str, api_key: str, client_ssl_config: ClientSSLConfig
) -> ClientWSConfig:
    return ClientWSConfig(server_url=ws_url, api_key=api_key, ssl=client_ssl_config)


@pytest.fixture
def client_config(
    client_source_config: ReaderConfig,
    client_sink_config: WriterConfig,
    client_ws_config: ClientWSConfig,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=client_ws_config,
        source=client_source_config,
        sink=client_sink_config,
    )


@pytest.fixture
def var_client_config(
    var_source_config: ReaderConfig,
    var_sink_config: WriterConfig,
    client_ws_config: ClientWSConfig,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=client_ws_config,
        source=var_source_config,
        sink=var_sink_config,
    )


@pytest_asyncio.fixture
async def client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with ClientService(client_config) as service:
        yield service


@pytest_asyncio.fixture
async def var_client(
    var_client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with ClientService(var_client_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_cert_client(
    client_config: ClientServiceConfig,
    another_cert: SignedCertKey,
) -> AsyncGenerator[ClientService]:
    another_cert_config = copy.deepcopy(client_config)
    ssl = another_cert_config.websockets.ssl
    ssl.cert_file = another_cert.cert_file
    ssl.key_file = another_cert.key_file
    async with ClientService(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_apikey_client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    another_apikey_config = copy.deepcopy(client_config)
    another_apikey_config.websockets.api_key = fake.passport_number()
    async with ClientService(another_apikey_config) as service:
        yield service


@pytest_asyncio.fixture
async def nossl_client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with ClientService(client_config) as service:
        service._ssl_context = None
        service._upstream_url = service._upstream_url.replace("wss://", "ws://")
        service._downstream_url = service._downstream_url.replace("wss://", "ws://")
        yield service


@pytest_asyncio.fixture
async def started_client_side(
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
    client: ClientService,
) -> None:
    client_writer.start()
    client_reader.start()

    asyncio.create_task(client.run())
    await client.started.wait()
