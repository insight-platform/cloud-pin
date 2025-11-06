import asyncio
import unittest.mock
from datetime import timedelta
from unittest.mock import Mock, call

import opentelemetry.metrics._internal
import pytest
from aiohttp import ClientSession
from freezegun import freeze_time
from opentelemetry.util._once import Once
from vcr.cassette import Cassette

from savant_cloudpin.cfg import (
    HealthConfig,
    MetricsConfig,
    OTLPMetricConfig,
    PrometheusConfig,
)
from savant_cloudpin.observability import serve_health_endpoint, serve_metrics
from savant_cloudpin.services._measuring import Measurements, Metrics, ServiceSide
from tests.helpers.messages import MessageData


@pytest.fixture(params=["Client", "Server"])
def service_type(request: pytest.FixtureRequest) -> ServiceSide:
    return request.param


@pytest.mark.asyncio
async def test_health(
    health_config: HealthConfig, client_session: ClientSession
) -> None:
    async with serve_health_endpoint(health_config):
        response = await client_session.get(health_config.endpoint)

        assert response.status == 200
        assert await response.text() == "OK"


@pytest.fixture
def reset_meter_provider() -> None:
    opentelemetry.metrics._internal._METER_PROVIDER_SET_ONCE = Once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_meter_provider")
async def test_prometheus(
    prometheus_config: PrometheusConfig,
    prometheus_base_url: str,
    service_type: ServiceSide,
    client_session: ClientSession,
) -> None:
    expected_line = f'ws_connected_total{{service="{service_type}"}} 1.0'
    config = MetricsConfig(prometheus=prometheus_config)
    measurements = Measurements(service_type, config)
    async with serve_metrics(config):
        measurements.metrics.reset_meter_provider()
        measurements.increment_ws_connected()

        responses = list[tuple[int, str]]()
        for _ in range(5):
            response = await client_session.get(f"{prometheus_base_url}/metrics")
            responses.append((response.status, await response.text()))
            await asyncio.sleep(0.1)

        assert any(
            status == 200 and expected_line in content.splitlines()
            for status, content in responses
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_meter_provider")
@pytest.mark.vcr()
async def test_otlp_metrics(
    otlp_metric_config: OTLPMetricConfig,
    otlp_base_url: str,
    service_type: ServiceSide,
    vcr_cassette: Cassette,
) -> None:
    expected_status = {"code": 200, "message": "OK"}
    expected_url = f"{otlp_base_url}/v1/metrics"
    config = MetricsConfig(otlp=otlp_metric_config)
    measurements = Measurements(service_type, config)
    async with serve_metrics(config):
        measurements.metrics.reset_meter_provider()

        timeout = asyncio.create_task(asyncio.sleep(5))
        while not vcr_cassette.play_count and not timeout.done():
            measurements.measure_sink_message_data(b"abc")
            await asyncio.sleep(0.2)

        assert vcr_cassette.play_count > 0
        assert any(
            b"message_size" in req.body
            and res["status"] == expected_status
            and req.uri == expected_url
            for req, res in zip(vcr_cassette.requests, vcr_cassette.responses)
        )


@unittest.mock.patch.object(Metrics, "delay")
def test_measurements_for_video_frame(delay_mock: Mock) -> None:
    client_measurements = Measurements("Client", None)
    server_measurements = Measurements("Server", None)
    msg = MessageData.fake_video_frame().to_message()

    with freeze_time("2025-11-11", tz_offset=0) as frozen_time:
        msg = client_measurements.measure_source_message(msg)
        frozen_time.tick(delta=timedelta(seconds=2))
        msg = server_measurements.measure_sink_message(msg)
        frozen_time.tick(delta=timedelta(seconds=10))
        msg = server_measurements.measure_source_message(msg)
        frozen_time.tick(delta=timedelta(seconds=3))
        msg = client_measurements.measure_sink_message(msg)

    assert delay_mock.record.called
    assert delay_mock.record.call_args_list == [
        call(2.0, {"service": "Server", "path_start": "Client", "path_end": "Server"}),
        call(2.0, {"service": "Server", "path_start": "Client", "path_end": "Server"}),
        call(10.0, {"service": "Server", "path_start": "Server", "path_end": "Server"}),
        call(2.0, {"service": "Client", "path_start": "Client", "path_end": "Server"}),
        call(10.0, {"service": "Client", "path_start": "Server", "path_end": "Server"}),
        call(3.0, {"service": "Client", "path_start": "Server", "path_end": "Client"}),
        call(15.0, {"service": "Client", "path_start": "Client", "path_end": "Client"}),
    ]
