from collections.abc import AsyncGenerator, Generator
from typing import Literal

import pytest
import pytest_asyncio

from savant_cloudpin.cfg import SinkConfig, SourceConfig
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


@pytest_asyncio.fixture
async def source_port(connect_dir_pair: ConnectDirPair) -> AsyncGenerator[int]:
    async with PortPool().lease() as port:
        yield port


@pytest.fixture
def source(connect_dir_pair: ConnectDirPair, source_port: int) -> Generator[Writer]:
    con = DIR_OPPOSITES[connect_dir_pair[0]]
    cfg = SinkConfig(
        max_infight_messages=1,
        url=f"dealer+{con}:tcp://127.0.0.1:{source_port}",
        send_timeout=100,
        receive_timeout=100,
    )
    with Writer(cfg) as writer:
        yield writer


@pytest_asyncio.fixture
async def sink_port(connect_dir_pair: ConnectDirPair) -> AsyncGenerator[int]:
    async with PortPool().lease() as port:
        yield port


@pytest.fixture
def sink(connect_dir_pair: ConnectDirPair, sink_port: int) -> Generator[Reader]:
    con = DIR_OPPOSITES[connect_dir_pair[1]]
    cfg = SourceConfig(
        results_queue_size=1,
        url=f"router+{con}:tcp://127.0.0.1:{sink_port}",
        receive_timeout=100,
    )
    with Reader(cfg) as reader:
        yield reader


@pytest.fixture
def client_service(
    connect_dir_pair: ConnectDirPair,
    source_port: int,
    sink_port: int,
) -> Generator[ClientService]:
    source_con, sink_con = connect_dir_pair
    source_cfg = SourceConfig(
        results_queue_size=10,
        url=f"router+{source_con}:tcp://127.0.0.1:{source_port}",
        receive_timeout=100,
    )
    sink_cfg = SinkConfig(
        max_infight_messages=10,
        url=f"dealer+{sink_con}:tcp://127.0.0.1:{sink_port}",
        send_timeout=100,
        receive_timeout=100,
    )
    with ClientService(source_cfg, sink_cfg) as service:
        yield service
