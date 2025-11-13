import asyncio

from savant_rs.py.log import get_logger, init_logging

from savant_cloudpin.cfg import SENSITIVE_KEYS, dump_to_yaml, load_config
from savant_cloudpin.observability import serve_health_endpoint, serve_metrics
from savant_cloudpin.services import create_service
from savant_cloudpin.signals import handle_signals


async def serve() -> None:
    config = load_config()

    init_logging(config.log.spec)
    logger = get_logger(__name__)

    logger.info("Configuration loaded")
    config_yaml = dump_to_yaml(config, scrape_keys=SENSITIVE_KEYS)
    logger.debug(f"Configuration details:\n{config_yaml}")

    logger.info("Running main loop ...")
    async with (
        handle_signals() as handler,
        serve_health_endpoint(config.health),
        serve_metrics(config.metrics),
        create_service(config) as service,
    ):
        handler.append(service.stop_running)

        await service.run()
    logger.info("Main loop stopped")


asyncio.run(serve())
