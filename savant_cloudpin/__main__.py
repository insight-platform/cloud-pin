import asyncio

from savant_rs.py.log import get_logger, init_logging

from savant_cloudpin.cfg import SENSITIVE_KEYS, dump_to_yaml, load_config
from savant_cloudpin.services import create_service


async def serve() -> None:
    config = load_config()

    init_logging(config.observability.log_spec)
    logger = get_logger(__name__)

    logger.info("Configuration loaded")
    config_yaml = dump_to_yaml(config, scrape_keys=SENSITIVE_KEYS)
    logger.debug(f"Configuration details:\n{config_yaml}")

    logger.info("Running main loop ...")
    async with create_service(config) as service:
        await service.run()
    logger.info("Main loop stopped")


asyncio.run(serve())
