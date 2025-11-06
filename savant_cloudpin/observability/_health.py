from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from aiohttp.web import Application, AppRunner, Request, Response, TCPSite
from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import HealthConfig
from savant_cloudpin.observability._utils import none_arg_returns, noop_agen

logger = get_logger(__package__ or __name__)


async def health(_: Request) -> Response:
    return Response(text="OK", status=200)


@asynccontextmanager
@none_arg_returns(noop_agen)
async def serve_health_endpoint(config: HealthConfig) -> AsyncGenerator:
    url = urlparse(config.endpoint)
    if not url.scheme or url.scheme != "http":
        raise ValueError(f"Unsupported scheme for health endpoint {url.scheme}")
    path = url.path
    port = url.port or 8080
    host = url.hostname
    url = f"http://{host}:{port}{url.path}"

    app = Application()
    app.router.add_get(path, health)
    runner = AppRunner(app)
    try:
        await runner.setup()
        site = TCPSite(runner, host, port)
        await site.start()
        logger.info(f"Health check endpoint at {url}")
        yield
    finally:
        logger.info(f"Stop health check endpoint at {url}")
        await runner.cleanup()
