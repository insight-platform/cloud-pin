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
    ZMQReaderConfig,
    ZMQWriterConfig,
)
from savant_cloudpin.services import ClientService, create_service
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.ssl import SignedCertKey

fake = Faker()


@pytest.fixture
def client_ws_config(
    ws_endpoint: str, api_key: str, client_ssl_config: ClientSSLConfig
) -> ClientWSConfig:
    return ClientWSConfig(
        endpoint=ws_endpoint,
        api_key=api_key,
        ssl=client_ssl_config,
        reconnect_timeout=0.01,
    )


@pytest.fixture
def client_config(
    client_zmq_src_config: ZMQReaderConfig,
    client_zmq_sink_config: ZMQWriterConfig,
    client_ws_config: ClientWSConfig,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=client_ws_config,
        zmq_src=client_zmq_src_config,
        zmq_sink=client_zmq_sink_config,
    )


@pytest.fixture
def var_client_config(
    var_zmq_src_config: ZMQReaderConfig,
    var_zmq_sink_config: ZMQWriterConfig,
    client_ws_config: ClientWSConfig,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=client_ws_config,
        zmq_src=var_zmq_src_config,
        zmq_sink=var_zmq_sink_config,
    )


@pytest_asyncio.fixture
async def client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with create_service(client_config) as service:
        yield service


@pytest_asyncio.fixture
async def var_client(
    var_client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with create_service(var_client_config) as service:
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
    async with create_service(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_apikey_client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    another_apikey_config = copy.deepcopy(client_config)
    another_apikey_config.websockets.api_key = fake.passport_number()
    async with create_service(another_apikey_config) as service:
        yield service


@pytest_asyncio.fixture
async def nossl_client(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    config = copy.deepcopy(client_config)
    config.websockets.endpoint = config.websockets.endpoint.replace("wss://", "ws://")
    config.websockets.ssl = ClientSSLConfig(insecure=True, check_hostname=False)
    async with create_service(config) as service:
        yield service


@pytest_asyncio.fixture
async def started_client_side(
    client_zmq_writer: NonBlockingWriter,
    client_zmq_reader: NonBlockingReader,
    client: ClientService,
) -> None:
    client_zmq_writer.start()
    client_zmq_reader.start()

    asyncio.create_task(client.run())
    await client.started.wait()
