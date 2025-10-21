import asyncio

from savant_cloudpin.cfg import load_config
from savant_cloudpin.services import ClientService

if __name__ == "__main__":
    config = load_config()
    with ClientService(config.source, config.sink) as service:
        asyncio.run(service.run())
