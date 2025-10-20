import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path


from filelock import FileLock, Timeout

MIN_PORT = 15000
MAX_PORT = 15031
LOCK_RESERVE_STEP = 10
LOCK_DIR = Path(".cache/PortPool")
PORT_LEASE_DELAY = 0.5


class PortPool:
    def _reserve_filelocks(self) -> None:
        file_ports = {
            int(file.name.removesuffix(".lock")) for file in LOCK_DIR.glob("*.lock")
        }
        for port in range(MIN_PORT, MAX_PORT + 1):
            if port not in file_ports:
                with FileLock(LOCK_DIR / f"{port}.lock", blocking=False):
                    pass

    @asynccontextmanager
    async def _create_port_lease(self) -> AsyncGenerator[int]:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self._reserve_filelocks()

        for port in range(MIN_PORT, MAX_PORT + 1):
            filelock = FileLock(LOCK_DIR / f"{port}.lock", blocking=False)
            try:
                with filelock as lock:
                    with lock.acquire(timeout=0):
                        yield port
                        await asyncio.sleep(PORT_LEASE_DELAY)
                break
            except Timeout:
                continue

    def lease(self) -> AbstractAsyncContextManager[int]:
        return self._create_port_lease()
