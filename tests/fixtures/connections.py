from collections.abc import Generator
from typing import Literal

import pytest
from faker import Faker

from tests.helpers.ports import PortPool

type ConnectDir = Literal["bind", "connect"]
type ConnectDirPair = tuple[ConnectDir, ConnectDir]
type SocketType = Literal["tcp", "ipc"]


DIR_OPPOSITES: dict[ConnectDir, ConnectDir] = {
    "bind": "connect",
    "connect": "bind",
}

fake = Faker()


def opposite_dir(dir: ConnectDir | str) -> ConnectDir:
    if dir not in ("bind", "connect"):
        raise ValueError(f"Invalid connection direction {dir}")
    return DIR_OPPOSITES[dir]


def opposite_dir_url(url: str) -> str:
    dir, common_url = url.split(":", 1)
    return f"{opposite_dir(dir)}:{common_url}"


@pytest.fixture(params=["bind", "connect"])
def connect_dir1(request: pytest.FixtureRequest) -> ConnectDir:
    return request.param


@pytest.fixture(params=["bind", "connect"])
def connect_dir2(request: pytest.FixtureRequest) -> ConnectDir:
    return request.param


@pytest.fixture(params=["tcp", "ipc"])
def socket_type(request: pytest.FixtureRequest) -> SocketType:
    return request.param


@pytest.fixture(scope="session")
def port_pool() -> Generator[PortPool]:
    with PortPool() as pool:
        yield pool


@pytest.fixture
def api_key() -> str:
    return fake.passport_number()


@pytest.fixture
def ws_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"wss://127.0.0.1:{port}/"
