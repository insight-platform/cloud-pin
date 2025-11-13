from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import urlparse, urlunparse

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import (
    MetricReader,
    PeriodicExportingMetricReader,
)
from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import OTLPMetricConfig
from savant_cloudpin.observability._utils import none_arg_returns, noop_agen

logger = get_logger(__package__ or __name__)


@asynccontextmanager
@none_arg_returns(noop_agen)
async def serve_otlp_exporter(
    config: OTLPMetricConfig, readers: list[MetricReader]
) -> AsyncGenerator:
    scheme, netloc, path, params, query, fragment = urlparse(config.endpoint)
    if not scheme or scheme != "http":
        raise ValueError(f"Unsupported scheme for health endpoint {scheme}")
    if not config.custom_path:
        path = "/v1/metrics"

    url = urlunparse([scheme, netloc, path, params, query, fragment])
    logger.info(f"OTLP Collector export to {url}")
    periodic_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(url),
        export_interval_millis=max(1, int(config.export_timeout * 1000)),
    )
    readers.append(periodic_reader)
    try:
        yield
    finally:
        logger.info(f"Stop OTLP Collector export to {url}")
