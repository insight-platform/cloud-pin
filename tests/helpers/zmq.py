import asyncio

from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.zmq import NonBlockingReader, ReaderResult


async def receive_results(
    reader: NonBlockingReader, count: int, *, timeout: float = 5
) -> list[ReaderResult | None]:
    result = list[ReaderResult | None]()

    async def repeat_receive() -> None:
        while not reader.is_shutdown() and len(result) < count:
            while msg := reader.try_receive():
                if isinstance(msg, ReaderResultMessage):
                    result.append(msg)
            await asyncio.sleep(0.001)

    try:
        await asyncio.wait_for(repeat_receive(), timeout)
    except TimeoutError:
        pass
    return result


async def receive_result(
    reader: NonBlockingReader, *, timeout: float = 3
) -> ReaderResult | None:
    results = await receive_results(reader, count=1, timeout=timeout)
    return results[0] if results else None
