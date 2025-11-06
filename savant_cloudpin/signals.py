import asyncio
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from signal import SIGINT, SIGTERM, Signals

from savant_rs.py.log import get_logger

__all__ = ["SignalHandler", "handle_signals"]

logger = get_logger(__package__ or __name__)
type Finalizer = Callable[[], None]


class SignalHandler:
    def __init__(self) -> None:
        self._handlers = list[Finalizer]()

    def _call(self, *args) -> None:
        logger.info("Signaled finalizing ...")

        for finalizer in self._handlers:
            finalizer()

    def append(self, handler: Finalizer) -> None:
        logger.debug("Registered signal finalizer")
        self._handlers.append(handler)


@asynccontextmanager
async def handle_signals(
    signals: Sequence = (SIGTERM, SIGINT),
) -> AsyncGenerator[SignalHandler]:
    signames = ", ".join(Signals(sig).name for sig in signals)
    handler = SignalHandler()
    loop = asyncio.get_running_loop()
    for sig in signals:
        loop.add_signal_handler(sig, handler._call)

    logger.debug(f"Signal handling {signames} ...")
    try:
        yield handler
    finally:
        logger.debug(f"Stop signal handling {signames}")
        for sig in signals:
            loop.remove_signal_handler(sig)
