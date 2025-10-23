from abc import abstractmethod
from asyncio import Event
from contextlib import AbstractAsyncContextManager
from typing import override


class ServiceBase[T](AbstractAsyncContextManager[T]):
    def __init__(self) -> None:
        self.running = False
        self.started = Event()
        self.stopped = Event()
        self.stopped.set()

    @abstractmethod
    async def _serve(self) -> None: ...

    async def run(self) -> None:
        self.stopped.clear()
        self.running = True
        try:
            await self._serve()
        finally:
            self.running = False
            self.started.clear()
            self.stopped.set()

    async def stop(self) -> None:
        self.running = False
        await self.stopped.wait()

    @override
    async def __aexit__(self, *args) -> bool | None:
        await self.stop()
        return None
