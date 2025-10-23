import copy
from collections.abc import AsyncGenerator, Generator
from typing import Literal

import pytest
import pytest_asyncio
from faker import Faker
from savant_rs.zmq import ReaderConfigBuilder, WriterConfigBuilder

from savant_cloudpin.cfg import ReaderConfig, WriterConfig
from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    SSLCertConfig,
)
from savant_cloudpin.services import ClientService, ServerService
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.ports import PortPool
from tests.helpers.ssl import TestSSLFiles, ensure_ssl_files

type ConnectDir = Literal["bind", "connect"]
type ConnectDirPair = tuple[ConnectDir, ConnectDir]


fake = Faker()

DIR_OPPOSITES: dict[ConnectDir, ConnectDir] = {
    "bind": "connect",
    "connect": "bind",
}


@pytest.fixture
def test_ssl_files() -> TestSSLFiles:
    return ensure_ssl_files()


@pytest.fixture(
    params=[
        ("bind", "bind"),
        ("bind", "connect"),
        ("connect", "bind"),
        ("connect", "connect"),
    ],
    ids=lambda pair: " | ".join(pair),
)
def connect_dir_pair(request: pytest.FixtureRequest) -> ConnectDirPair:
    return request.param


@pytest.fixture(params=["tcp", "ipc"])
def socket_type(request: pytest.FixtureRequest) -> Literal["tcp", "ipc"]:
    return request.param


@pytest_asyncio.fixture
async def source_common_url(socket_type: Literal["tcp", "ipc"]) -> AsyncGenerator[str]:
    async with PortPool().lease() as port:
        if socket_type == "tcp":
            yield f"tcp://127.0.0.1:{port}"
        else:
            yield f"ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def source_url(connect_dir_pair: ConnectDirPair, source_common_url: str) -> str:
    con = DIR_OPPOSITES[connect_dir_pair[0]]
    return f"dealer+{con}:{source_common_url}"


@pytest.fixture
def source_service_url(connect_dir_pair: ConnectDirPair, source_common_url: str) -> str:
    con = connect_dir_pair[0]
    return f"{con}:{source_common_url}"


@pytest.fixture
def source(source_url: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(source_url)
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    writer = NonBlockingWriter(cfg.build(), max_inflight_messages=1)
    yield writer
    if writer.is_started():
        writer.shutdown()


@pytest_asyncio.fixture
async def sink_common_url(socket_type: Literal["tcp", "ipc"]) -> AsyncGenerator[str]:
    async with PortPool().lease() as port:
        if socket_type == "tcp":
            yield f"tcp://127.0.0.1:{port}"
        else:
            yield f"ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def sink_url(connect_dir_pair: ConnectDirPair, sink_common_url: str) -> str:
    con = DIR_OPPOSITES[connect_dir_pair[1]]
    return f"router+{con}:{sink_common_url}"


@pytest.fixture
def sink_service_url(connect_dir_pair: ConnectDirPair, sink_common_url: str) -> str:
    con = connect_dir_pair[1]
    return f"{con}:{sink_common_url}"


@pytest.fixture
def sink(sink_url: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(sink_url)
    cfg.with_receive_timeout(100)
    reader = NonBlockingReader(cfg.build(), results_queue_size=1)
    yield reader
    if reader.is_started():
        reader.shutdown()


@pytest.fixture
def api_key() -> str:
    return fake.passport_number()


@pytest_asyncio.fixture
async def ws_url() -> AsyncGenerator[str]:
    async with PortPool().lease() as port:
        yield f"wss://127.0.0.1:{port}/"


@pytest.fixture
def client_source_config(source_service_url: str) -> ReaderConfig:
    return ReaderConfig(
        results_queue_size=10, url=source_service_url, receive_timeout=100
    )


@pytest.fixture
def client_sink_config(sink_service_url: str) -> WriterConfig:
    return WriterConfig(
        max_inflight_messages=10,
        url=sink_service_url,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def client_config(
    client_source_config: ReaderConfig,
    client_sink_config: WriterConfig,
    ws_url: str,
    api_key: str,
    test_ssl_files: TestSSLFiles,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=ClientWSConfig(
            server_url=ws_url,
            api_key=api_key,
            ssl=ClientSSLConfig(
                disable_client_auth=False,
                check_hostname=False,
                server=SSLCertConfig(test_ssl_files.server.certificate_path),
                client=test_ssl_files.client,
            ),
        ),
        source=client_source_config,
        sink=client_sink_config,
    )


@pytest_asyncio.fixture
async def client_service(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    async with ClientService(client_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_cert_client_service(
    client_config: ClientServiceConfig,
    test_ssl_files: TestSSLFiles,
) -> AsyncGenerator[ClientService]:
    another_cert_client_config = copy.deepcopy(client_config)
    another_cert_client_config.websockets.ssl.client = test_ssl_files.another_client
    async with ClientService(another_cert_client_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_apikey_client_service(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    another_apikey_client_config = copy.deepcopy(client_config)
    another_apikey_client_config.websockets.api_key = fake.passport_number()
    async with ClientService(another_apikey_client_config) as service:
        yield service


@pytest.fixture
def server_config(
    ws_url: str, api_key: str, test_ssl_files: TestSSLFiles
) -> ServerServiceConfig:
    return ServerServiceConfig(
        io_timeout=0.01,
        websockets=ServerWSConfig(
            server_url=ws_url,
            api_key=api_key,
            disable_ssl=False,
            ssl=ServerSSLConfig(
                disable_client_auth=False,
                server=test_ssl_files.server,
                client=SSLCertConfig(test_ssl_files.client.certificate_path),
            ),
        ),
        source=ReaderConfig(results_queue_size=10, url="unknown"),
        sink=WriterConfig(max_inflight_messages=10, url="unknown"),
    )


@pytest_asyncio.fixture
async def server_service(
    server_config: ServerServiceConfig,
) -> AsyncGenerator[ServerService]:
    async with ServerService(server_config) as service:
        yield service
