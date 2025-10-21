from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import asdict
from typing import Self

from savant_rs.utils.serialization import Message
from savant_rs.zmq import (
    NonBlockingReader,
    NonBlockingWriter,
    ReaderConfigBuilder,
    ReaderResultMessage,
    ReaderResultPrefixMismatch,
    ReaderResultTimeout,
    WriteOperationResult,
    WriterConfigBuilder,
)

from savant_cloudpin.cfg import ReaderConfig, WriterConfig

type ReaderResult = (
    ReaderResultMessage | ReaderResultTimeout | ReaderResultPrefixMismatch
)


class Reader(AbstractContextManager["Reader"]):
    def __init__(self, config: ReaderConfig) -> None:
        cfg = ReaderConfigBuilder(config.url)
        cfg.with_map_config(
            _to_map_config(config, excluded=("url", "results_queue_size"))
        )
        self._reader = NonBlockingReader(cfg.build(), config.results_queue_size)
        self._queue_size = config.results_queue_size

    def is_empty(self) -> bool:
        return self._reader.enqueued_results() == 0

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
        if not self._reader.is_started() or self._reader.is_shutdown():
            return

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

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args) -> bool | None:
        self.shutdown()
        return None


class Writer(AbstractContextManager["Writer"]):
    def __init__(self, config: WriterConfig) -> None:
        cfg = WriterConfigBuilder(config.url)
        cfg.with_map_config(
            _to_map_config(config, excluded=("url", "max_infight_messages"))
        )
        self._writer = NonBlockingWriter(cfg.build(), config.max_infight_messages)
        self._queue_size = config.max_infight_messages

    def has_capacity(self) -> bool:
        return self._writer.inflight_messages() < self._queue_size

    def start(self) -> None:
        return self._writer.start()

    def shutdown(self) -> None:
        if self._writer.is_started() and not self._writer.is_shutdown():
            self._writer.shutdown()

    def send(
        self, topic: bytes, message: Message, extra_data: bytes | None = None
    ) -> WriteOperationResult:
        return self._writer.send_message(topic.decode(), message, extra_data or b"")  # type: ignore

    def send_eos(self, topic: bytes) -> WriteOperationResult:
        return self._writer.send_eos(topic.decode())

    def __enter__(self) -> "Writer":
        return self

    def __exit__(self, *args) -> bool | None:
        self.shutdown()


def _to_map_config(
    config: ReaderConfig | WriterConfig, /, excluded: tuple[str, ...]
) -> dict[str, str | int]:
    return {
        key: val
        for key, val in asdict(config).items()
        if isinstance(key, str) and isinstance(val, (str, int))
        if key not in excluded
    }
