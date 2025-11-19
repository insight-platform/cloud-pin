from collections.abc import Generator

import pytest

from savant_cloudpin.cfg import HealthConfig, OTLPMetricConfig, PrometheusConfig
from tests.helpers.ports import PortPool


@pytest.fixture
def health_config(port_pool: PortPool) -> Generator[HealthConfig]:
    with port_pool.lease() as port:
        yield HealthConfig(endpoint=f"http://127.0.0.1:{port}/healthz")


@pytest.fixture
def prometheus_base_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"http://127.0.0.1:{port}"


@pytest.fixture
def prometheus_config(prometheus_base_endpoint: str) -> PrometheusConfig:
    return PrometheusConfig(endpoint=prometheus_base_endpoint)


@pytest.fixture
def otlp_base_endpoint() -> str:
    return "http://otlp-collector:4318"


@pytest.fixture
def otlp_metric_config(otlp_base_endpoint: str) -> OTLPMetricConfig:
    return OTLPMetricConfig(endpoint=otlp_base_endpoint, export_timeout=0.1)
