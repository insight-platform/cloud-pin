from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from aiohttp import hdrs
from aiohttp.web import (
    Application,
    AppRunner,
    Request,
    Response,
    RouteTableDef,
    TCPSite,
)
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics.export import MetricReader
from prometheus_client.exposition import choose_encoder
from prometheus_client.registry import REGISTRY
from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import PrometheusConfig
from savant_cloudpin.observability._utils import none_arg_returns, noop_agen

logger = get_logger(__package__ or __name__)
routes = RouteTableDef()


async def metrics(request: Request) -> Response:
    # based on prometheus_client.aiohttp.exposition, which isn't included in prometheus-client==0.23.1

    if "name[]" in request.query:
        names = request.query.getall("name[]")
        registry = REGISTRY.restricted_registry(names)
    else:
        registry = REGISTRY

    accept_header = ",".join(request.headers.getall(hdrs.ACCEPT, []))
    encoder, content_type = choose_encoder(accept_header)
    body = encoder(registry)  # type: ignore
    return Response(status=200, headers=[("Content-Type", content_type)], body=body)


@asynccontextmanager
@none_arg_returns(noop_agen)
async def serve_prometheus_exporter(
    config: PrometheusConfig, readers: list[MetricReader]
) -> AsyncGenerator:
    url = urlparse(config.endpoint)
    if not url.scheme or url.scheme != "http":
        raise ValueError(f"Unsupported scheme for health endpoint {url.scheme}")
    path = url.path if config.custom_path else "/metrics"
    port = url.port or 8080
    host = url.hostname
    url = f"http://{host}:{port}{path}"

    prometheus_reader = PrometheusMetricReader()
    readers.append(prometheus_reader)

    app = Application()
    app.router.add_get(path, metrics)
    runner = AppRunner(app)
    try:
        await runner.setup()
        site = TCPSite(runner, host, port)
        await site.start()
        logger.info(f"Prometheus export at {url}")
        yield
    finally:
        logger.info(f"Stop Prometheus export at {url}")
        await runner.cleanup()
