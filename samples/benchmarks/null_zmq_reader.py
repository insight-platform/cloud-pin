import os
import signal
import time
from pathlib import Path
from signal import SIGTERM

from savant_rs.py.log import get_logger, init_logging
from savant_rs.zmq import NonBlockingReader, ReaderConfigBuilder, ReaderResultMessage

READY_PATH = os.environ.get("READY_PATH", None)
ZMQ_ENDPOINT = os.environ.get("ZMQ_ENDPOINT", None)
ZMQ_RESULTS_QUEUE_SIZE = os.environ.get("ZMQ_RESULTS_QUEUE_SIZE", "1000")
IO_TIMEOUT = os.environ.get("IO_TIMEOUT", "0.001")


def loop(
    endpoint: str,
    results_queue_size: int,
    ready_path: Path,
    io_timeout: float,
) -> None:
    logger = get_logger(__file__)
    cfg = ReaderConfigBuilder(endpoint)
    reader = NonBlockingReader(cfg.build(), results_queue_size=results_queue_size)
    reader.start()
    logger.info("Reading messages...")
    signal.signal(SIGTERM, lambda *args: reader.shutdown())
    ready = False
    if ready_path.exists():
        os.remove(ready_path)
    try:
        while not reader.is_shutdown():
            msg = reader.try_receive()
            if not ready and isinstance(msg, ReaderResultMessage):
                ready = True
                ready_path.touch()
            if not reader.enqueued_results():
                time.sleep(io_timeout)

    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stop reading messages")
        if not reader.is_shutdown():
            reader.shutdown()


if __name__ == "__main__":
    init_logging()
    assert READY_PATH and ZMQ_ENDPOINT
    loop(
        endpoint=ZMQ_ENDPOINT,
        results_queue_size=int(ZMQ_RESULTS_QUEUE_SIZE),
        ready_path=Path(READY_PATH),
        io_timeout=float(IO_TIMEOUT),
    )
