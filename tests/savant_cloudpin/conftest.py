import asyncio
import copy
from collections.abc import AsyncGenerator, Generator
from typing import Literal

import pytest
import pytest_asyncio
from faker import Faker
from savant_rs.zmq import ReaderConfigBuilder, WriterConfigBuilder

from savant_cloudpin.cfg import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    WriterConfig,
)
from savant_cloudpin.services import ClientService, ServerService
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests import helpers
from tests.helpers.ports import PortPool
from tests.helpers.ssl import CertificateAuthority, SignedCertKey

type ConnectDir = Literal["bind", "connect"]
type ConnectDirPair = tuple[ConnectDir, ConnectDir]


fake = Faker()

DIR_OPPOSITES: dict[ConnectDir, ConnectDir] = {
    "bind": "connect",
    "connect": "bind",
}


@pytest.fixture
def ca() -> CertificateAuthority:
    return helpers.ssl.prepare_ca("ca")


@pytest.fixture
def another_ca() -> CertificateAuthority:
    return helpers.ssl.prepare_ca("another_ca")


@pytest.fixture
def client_signed_cert(ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(ca.name, "client_signed_cert")


@pytest.fixture
def server_signed_cert(ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(ca.name, "server_signed_cert")


@pytest.fixture
def another_signed_cert(another_ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(another_ca.name, "another_signed_cert")


@pytest.fixture(
    params=[
        ("bind", "bind"),
        ("bind", "connect"),
        ("connect", "bind"),
        ("connect", "connect"),
    ],
    ids="|".join,
)
def connect_dir_pair(request: pytest.FixtureRequest) -> ConnectDirPair:
    return request.param


@pytest.fixture(scope="session")
def port_pool() -> Generator[PortPool]:
    with PortPool() as pool:
        yield pool


@pytest.fixture(params=["tcp", "ipc"])
def socket_type(request: pytest.FixtureRequest) -> Literal["tcp", "ipc"]:
    return request.param


@pytest.fixture
def source_common_url(
    port_pool: PortPool, socket_type: Literal["tcp", "ipc"]
) -> Generator[str]:
    with port_pool.lease() as port:
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


@pytest.fixture
def sink_common_url(
    port_pool: PortPool, socket_type: Literal["tcp", "ipc"]
) -> Generator[str]:
    with port_pool.lease() as port:
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


@pytest.fixture
def ws_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
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
    client_signed_cert: SignedCertKey,
) -> ClientServiceConfig:
    return ClientServiceConfig(
        io_timeout=0.01,
        websockets=ClientWSConfig(
            server_url=ws_url,
            api_key=api_key,
            ssl=ClientSSLConfig(
                ca_file=client_signed_cert.ca_file,
                cert_file=client_signed_cert.cert_file,
                key_file=client_signed_cert.key_file,
                check_hostname=False,
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
    another_signed_cert: SignedCertKey,
) -> AsyncGenerator[ClientService]:
    another_cert_config = copy.deepcopy(client_config)
    ssl = another_cert_config.websockets.ssl
    ssl.cert_file = another_signed_cert.cert_file
    ssl.key_file = another_signed_cert.key_file
    async with ClientService(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def another_apikey_client_service(
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ClientService]:
    another_apikey_config = copy.deepcopy(client_config)
    another_apikey_config.websockets.api_key = fake.passport_number()
    async with ClientService(another_apikey_config) as service:
        yield service


@pytest.fixture
def server_config(
    ws_url: str,
    api_key: str,
    server_signed_cert: SignedCertKey,
) -> ServerServiceConfig:
    return ServerServiceConfig(
        io_timeout=0.01,
        websockets=ServerWSConfig(
            server_url=ws_url,
            api_key=api_key,
            ssl=ServerSSLConfig(
                ca_file=server_signed_cert.ca_file,
                cert_file=server_signed_cert.cert_file,
                key_file=server_signed_cert.key_file,
                client_cert_required=True,
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


@pytest_asyncio.fixture
async def another_cert_server_service(
    server_config: ServerServiceConfig,
    another_signed_cert: SignedCertKey,
) -> AsyncGenerator[ServerService]:
    another_cert_config = copy.deepcopy(server_config)
    ssl = another_cert_config.websockets.ssl
    assert ssl is not None
    ssl.cert_file = another_signed_cert.cert_file
    ssl.key_file = another_signed_cert.key_file
    async with ServerService(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def same_cert_server_service(
    server_config: ServerServiceConfig,
    client_config: ClientServiceConfig,
) -> AsyncGenerator[ServerService]:
    another_cert_config = copy.deepcopy(server_config)
    ssl = another_cert_config.websockets.ssl
    client_ssl = client_config.websockets.ssl

    assert ssl is not None and client_ssl.cert_file and client_ssl.key_file
    ssl.cert_file = client_ssl.cert_file
    ssl.key_file = client_ssl.key_file

    async with ServerService(another_cert_config) as service:
        yield service


@pytest_asyncio.fixture
async def started_client_side(
    source: NonBlockingWriter, sink: NonBlockingReader, client_service: ClientService
) -> None:
    sink.start()
    source.start()

    asyncio.create_task(client_service.run())
    await client_service.started.wait()
