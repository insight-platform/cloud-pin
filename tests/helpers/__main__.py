import asyncio
import os
import sys
from asyncio import Event

from savant_rs.py.log import init_logging

from savant_cloudpin.cfg import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    MetricsConfig,
    ObservabilityConfig,
    OTLPMetricConfig,
    PrometheusConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerWSConfig,
    WriterConfig,
)
from savant_cloudpin.observability import serve_metrics
from savant_cloudpin.services import create_service
from savant_cloudpin.signals import handle_signals
from tests.helpers.connections import opposite_dir_url
from tests.helpers.pipelines import (
    init_telemetry_tracer,
    run_identity_pipeline,
    run_infinite_read,
    run_infinite_write,
)

SERVER_SOURCE_URL = os.environ.get(
    "TEST_CLOUDPIN_SERVER_SOURCE_URL", "bind:ipc://tmp/test_server_source"
)
SERVER_SINK_URL = os.environ.get(
    "TEST_CLOUDPIN_SERVER_SINK_URL", "bind:ipc://tmp/test_server_sink"
)
CLIENT_SOURCE_URL = os.environ.get(
    "TEST_CLOUDPIN_CLIENT_SOURCE_URL", "bind:ipc://tmp/test_client_source"
)
CLIENT_SINK_URL = os.environ.get(
    "TEST_CLOUDPIN_CLIENT_SINK_URL", "bind:ipc://tmp/test_client_sink"
)
WS_URL = os.environ.get("TEST_CLOUDPIN_WEBSOCKET_URL", "ws://127.0.0.1:15000")
API_KEY = os.environ.get("TEST_CLOUDPIN_API_KEY", "super_secret")
CLIENT_PROMETHEUS_URL = os.environ.get(
    "TEST_CLOUDPIN_CLIENT_PROMETHEUS_URL", "http://0.0.0.0:8081"
)
SERVER_PROMETHEUS_URL = os.environ.get(
    "TEST_CLOUDPIN_SERVER_PROMETHEUS_URL", "http://0.0.0.0:8082"
)
OTEL_TRACER_URL = os.environ.get(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otlp-collector:4318/v1/traces"
)
CLIENT_CONFIG = ClientServiceConfig(
    websockets=ClientWSConfig(
        endpoint=WS_URL,
        api_key=API_KEY,
        ssl=ClientSSLConfig(insecure=True, check_hostname=False),
    ),
    source=ReaderConfig(url=CLIENT_SOURCE_URL),
    sink=WriterConfig(url=CLIENT_SINK_URL),
    observability=ObservabilityConfig(
        metrics=MetricsConfig(
            prometheus=PrometheusConfig(endpoint=CLIENT_PROMETHEUS_URL),
            otlp=OTLPMetricConfig(endpoint=OTEL_TRACER_URL),
        )
    ),
)
SERVER_CONFIG = ServerServiceConfig(
    websockets=ServerWSConfig(
        endpoint=WS_URL,
        api_key=API_KEY,
    ),
    sink=WriterConfig(url=SERVER_SINK_URL),
    source=ReaderConfig(url=SERVER_SOURCE_URL),
    observability=ObservabilityConfig(
        metrics=MetricsConfig(
            prometheus=PrometheusConfig(endpoint=SERVER_PROMETHEUS_URL),
            otlp=OTLPMetricConfig(endpoint=OTEL_TRACER_URL),
        )
    ),
)


match sys.argv[1]:
    case "identity_pipeline":

        async def serve() -> None:
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_identity_pipeline(
                    source_url=opposite_dir_url(SERVER_SINK_URL),
                    sink_url=opposite_dir_url(SERVER_SOURCE_URL),
                ),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "infinite_write":

        async def serve() -> None:
            init_telemetry_tracer(OTEL_TRACER_URL)
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_infinite_write(opposite_dir_url(CLIENT_SOURCE_URL)),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "infinite_read":

        async def serve() -> None:
            init_telemetry_tracer(OTEL_TRACER_URL)
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_infinite_read(opposite_dir_url(CLIENT_SINK_URL)),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "server":

        async def serve() -> None:
            async with (
                handle_signals() as handler,
                serve_metrics(SERVER_CONFIG.observability.metrics),
                create_service(SERVER_CONFIG) as service,
            ):
                handler.append(service.stop_running)

                await service.run()
    case "client":

        async def serve() -> None:
            async with (
                handle_signals() as handler,
                serve_metrics(CLIENT_CONFIG.observability.metrics),
                create_service(CLIENT_CONFIG) as service,
            ):
                handler.append(service.stop_running)

                await service.run()
    case _:

        async def serve() -> None:
            pass


init_logging("debug")
asyncio.run(serve())
