from collections.abc import AsyncGenerator, Generator
from typing import Literal

import pytest
import pytest_asyncio

from savant_cloudpin.cfg import ReaderConfig, WriterConfig
from savant_cloudpin.services import ClientService
from savant_cloudpin.zmq import Reader, Writer
from tests.helpers.ports import PortPool

type ConnectDir = Literal["bind", "connect"]
type ConnectDirPair = tuple[ConnectDir, ConnectDir]


DIR_OPPOSITES: dict[ConnectDir, ConnectDir] = {
    "bind": "connect",
    "connect": "bind",
}


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
def source(source_url: str) -> Generator[Writer]:
    cfg = WriterConfig(
        max_infight_messages=1, url=source_url, send_timeout=100, receive_timeout=100
    )
    with Writer(cfg) as writer:
        yield writer


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
def sink(sink_url: str) -> Generator[Reader]:
    cfg = ReaderConfig(results_queue_size=1, url=sink_url, receive_timeout=100)
    with Reader(cfg) as reader:
        yield reader


@pytest.fixture
def client_service(
    connect_dir_pair: ConnectDirPair,
    source_service_url: str,
    sink_service_url: str,
) -> Generator[ClientService]:
    source_con, sink_con = connect_dir_pair
    source_cfg = ReaderConfig(
        results_queue_size=10,
        url=source_service_url,
        receive_timeout=100,
    )
    sink_cfg = WriterConfig(
        max_infight_messages=10,
        url=sink_service_url,
        send_timeout=100,
        receive_timeout=100,
    )
    with ClientService(source_cfg, sink_cfg) as service:
        yield service
