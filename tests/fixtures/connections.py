from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from faker import Faker

from tests.helpers.connections import ConnectDir, SocketType
from tests.helpers.ports import PortPool

fake = Faker()


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
def ws_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"wss://127.0.0.1:{port}/"


@pytest_asyncio.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    async with ClientSession() as session:
        yield session
