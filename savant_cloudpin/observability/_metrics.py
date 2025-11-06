from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader

from savant_cloudpin.cfg import MetricsConfig
from savant_cloudpin.observability._otlp import serve_otlp_exporter
from savant_cloudpin.observability._prometheus import serve_prometheus_exporter
from savant_cloudpin.observability._utils import none_arg_returns, noop_agen


@asynccontextmanager
@none_arg_returns(noop_agen)
async def serve_metrics(config: MetricsConfig) -> AsyncGenerator:
    readers: list[MetricReader] = list[MetricReader]()
    async with (
        serve_otlp_exporter(config.otlp, readers),
        serve_prometheus_exporter(config.prometheus, readers),
    ):
        provider = MeterProvider(metric_readers=readers)
        set_meter_provider(provider)
        yield
        provider.force_flush()
        provider.shutdown()
