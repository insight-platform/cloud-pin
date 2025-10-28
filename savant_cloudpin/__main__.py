import asyncio

from savant_cloudpin.cfg import load_config
from savant_cloudpin.services import create_service


async def serve() -> None:
    config = load_config()
    async with create_service(config) as service:
        await service.run()


if __name__ == "__main__":
    asyncio.run(serve())
