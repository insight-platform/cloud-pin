import asyncio
from contextlib import AbstractContextManager

from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.cfg import SinkConfig, SourceConfig
from savant_cloudpin.zmq import Reader, Writer


class ClientService(AbstractContextManager["ClientService"]):
    def __init__(self, source: SourceConfig, sink: SinkConfig) -> None:
        self._source = Reader(source)
        self._sink = Writer(sink)
        self.running = False

    async def _loop(self) -> None:
        while self.running:
            await asyncio.sleep(0)
            msg = self._source.receive()
            if not isinstance(msg, ReaderResultMessage):
                continue

            await asyncio.sleep(0)
            self._sink.send(msg.topic, msg.message, msg.data(0))

    async def run(self) -> None:
        with self._source, self._sink:
            self._source.start()
            self._sink.start()

            self.running = True
            try:
                await self._loop()
            finally:
                self.running = False

    def stop(self) -> None:
        self.running = False

    def __enter__(self) -> "ClientService":
        return self

    def __exit__(self, *args) -> bool | None:
        self.stop()
        return None
