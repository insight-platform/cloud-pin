import time
from collections import deque
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from threading import Thread
from typing import override

from filelock import BaseFileLock, FileLock, Timeout

MIN_PORT = 15000
MAX_PORT = 15255
LOCK_DIR = Path(".cache/PortPool")
PORT_LEASE_DELAY = 0.5


class PortPool(AbstractContextManager["PortPool"]):
    def __init__(self) -> None:
        self._locks = deque[BaseFileLock]()
        self._stopped = False
        self._thread = Thread(target=self._release_loop)
        self._thread.start()

    def _release_loop(self) -> None:
        while not self._stopped:
            expired_locks = deque[BaseFileLock]()
            while self._locks:
                expired_locks.append(self._locks.pop())

            time.sleep(PORT_LEASE_DELAY)

            while expired_locks:
                expired_locks.pop().release()

    def reserve_filelocks(self) -> None:
        file_ports = {
            int(file.name.removesuffix(".lock")) for file in LOCK_DIR.glob("*.lock")
        }
        for port in range(MIN_PORT, MAX_PORT + 1):
            if port not in file_ports:
                with FileLock(LOCK_DIR / f"{port}.lock", blocking=False):
                    pass

    @contextmanager
    def _create_port_lease(self) -> Generator[int]:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self.reserve_filelocks()

        for port in range(MIN_PORT, MAX_PORT + 1):
            filelock = FileLock(LOCK_DIR / f"{port}.lock")
            if filelock.is_locked:
                continue
            try:
                filelock.acquire(timeout=0.00001)
                yield port
                self._locks.append(filelock)
                break
            except Timeout:
                continue

    def lease(self) -> AbstractContextManager[int]:
        return self._create_port_lease()

    @override
    def __exit__(self, exc_type, exc_value, traceback):
        self._stopped = True
        self._thread.join()
        return None
