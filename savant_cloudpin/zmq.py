from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from typing import override

from savant_rs import zmq
from savant_rs.utils.serialization import Message
from savant_rs.zmq import (
    ReaderResultMessage,
    ReaderResultPrefixMismatch,
    ReaderResultTimeout,
    WriteOperationResult,
)

__all__ = ["ReaderResult", "NonBlockingReader", "NonBlockingWriter"]

type ReaderResult = (
    ReaderResultMessage | ReaderResultTimeout | ReaderResultPrefixMismatch
)


class NonBlockingReader(AbstractContextManager["NonBlockingReader"]):
    def __init__(self, config: zmq.ReaderConfig, results_queue_size: int) -> None:
        self._reader = zmq.NonBlockingReader(config, results_queue_size)

    def is_empty(self) -> bool:
        return self._reader.enqueued_results() == 0

    def is_started(self) -> bool:
        return self._reader.is_started()

    def is_shutdown(self) -> bool:
        return self._reader.is_shutdown()

    def start(self) -> None:
        return self._reader.start()

    def _shutdown_safe(self) -> None:
        try:
            for _ in range(8):
                self._reader.try_receive()
            self._reader.shutdown()
        except RuntimeError:
            pass

    def shutdown(self) -> None:
        # workaround to avoid blocking by savant-rs internal channel
        with ThreadPoolExecutor(max_workers=1) as ex:
            cancellation = ex.submit(self._shutdown_safe)
            while cancellation.running():
                try:
                    self._reader.try_receive()
                except RuntimeError:
                    cancellation.cancel()
                    break

    def try_receive(self) -> ReaderResult | None:
        return self._reader.try_receive()

    def receive(self) -> ReaderResult:
        return self._reader.receive()

    @override
    def __exit__(self, *args) -> bool | None:
        self.shutdown()
        return None


class NonBlockingWriter(AbstractContextManager["NonBlockingWriter"]):
    def __init__(self, config: zmq.WriterConfig, max_inflight_messages: int) -> None:
        self._writer = zmq.NonBlockingWriter(config, max_inflight_messages)
        self._queue_size = max_inflight_messages

    def has_capacity(self) -> bool:
        return self._writer.inflight_messages() < self._queue_size

    def is_started(self) -> bool:
        return self._writer.is_started()

    def start(self) -> None:
        return self._writer.start()

    def shutdown(self) -> None:
        self._writer.shutdown()

    def send_message(
        self, topic: bytes, message: Message, extra_data: bytes | None = None
    ) -> WriteOperationResult:
        return self._writer.send_message(topic.decode(), message, extra_data or b"")  # type: ignore

    def send_eos(self, topic: bytes) -> WriteOperationResult:
        return self._writer.send_eos(topic.decode())

    @override
    def __exit__(self, *args) -> bool | None:
        self.shutdown()
