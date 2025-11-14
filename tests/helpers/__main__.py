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
    OTLPMetricConfig,
    PrometheusConfig,
    ServerServiceConfig,
    ServerWSConfig,
    ZMQReaderConfig,
    ZMQWriterConfig,
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

SERVER_ZMQ_SRC_ENDPOINT = os.environ.get(
    "SERVER_ZMQ_SRC_ENDPOINT", "bind:ipc://tmp/test_server_source"
)
SERVER_ZMQ_SINK_ENDPOINT = os.environ.get(
    "SERVER_ZMQ_SINK_ENDPOINT", "bind:ipc://tmp/test_server_sink"
)
CLIENT_ZMQ_SRC_ENDPOINT = os.environ.get(
    "CLIENT_ZMQ_SRC_ENDPOINT", "bind:ipc://tmp/test_client_source"
)
CLIENT_ZMQ_SINK_ENDPOINT = os.environ.get(
    "CLIENT_ZMQ_SINK_ENDPOINT", "bind:ipc://tmp/test_client_sink"
)
WEBSOCKETS_ENDPOINT = os.environ.get("WEBSOCKETS_ENDPOINT", "ws://127.0.0.1:15000")
API_KEY = os.environ.get("API_KEY", "super_secret")
CLIENT_METRICS_PROMETHEUS_ENDPOINT = os.environ.get(
    "CLIENT_METRICS_PROMETHEUS_ENDPOINT", "http://0.0.0.0:8081"
)
SERVER_METRICS_PROMETHEUS_ENDPOINT = os.environ.get(
    "SERVER_METRICS_PROMETHEUS_ENDPOINT", "http://0.0.0.0:8082"
)
OTLP_TRACES_ENDPOINT = os.environ.get(
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://otlp-collector:4318/v1/traces"
)
CLIENT_CONFIG = ClientServiceConfig(
    websockets=ClientWSConfig(
        endpoint=WEBSOCKETS_ENDPOINT,
        api_key=API_KEY,
        ssl=ClientSSLConfig(insecure=True, check_hostname=False),
    ),
    zmq_src=ZMQReaderConfig(endpoint=CLIENT_ZMQ_SRC_ENDPOINT),
    zmq_sink=ZMQWriterConfig(endpoint=CLIENT_ZMQ_SINK_ENDPOINT),
    metrics=MetricsConfig(
        prometheus=PrometheusConfig(endpoint=CLIENT_METRICS_PROMETHEUS_ENDPOINT),
        otlp=OTLPMetricConfig(endpoint=OTLP_TRACES_ENDPOINT),
    ),
)
SERVER_CONFIG = ServerServiceConfig(
    websockets=ServerWSConfig(
        endpoint=WEBSOCKETS_ENDPOINT,
        api_key=API_KEY,
    ),
    zmq_sink=ZMQWriterConfig(endpoint=SERVER_ZMQ_SINK_ENDPOINT),
    zmq_src=ZMQReaderConfig(endpoint=SERVER_ZMQ_SRC_ENDPOINT),
    metrics=MetricsConfig(
        prometheus=PrometheusConfig(endpoint=SERVER_METRICS_PROMETHEUS_ENDPOINT),
        otlp=OTLPMetricConfig(endpoint=OTLP_TRACES_ENDPOINT),
    ),
)


match sys.argv[1]:
    case "identity_pipeline":

        async def serve() -> None:
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_identity_pipeline(
                    zmq_src_endpoint=opposite_dir_url(SERVER_ZMQ_SINK_ENDPOINT),
                    zmq_sink_endpoint=opposite_dir_url(SERVER_ZMQ_SRC_ENDPOINT),
                ),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "infinite_write":

        async def serve() -> None:
            init_telemetry_tracer(OTLP_TRACES_ENDPOINT)
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_infinite_write(opposite_dir_url(CLIENT_ZMQ_SRC_ENDPOINT)),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "infinite_read":

        async def serve() -> None:
            init_telemetry_tracer(OTLP_TRACES_ENDPOINT)
            stopped = Event()
            async with (
                handle_signals() as handler,
                run_infinite_read(opposite_dir_url(CLIENT_ZMQ_SINK_ENDPOINT)),
            ):
                handler.append(stopped.set)
                await stopped.wait()
    case "server":

        async def serve() -> None:
            async with (
                handle_signals() as handler,
                serve_metrics(SERVER_CONFIG.metrics),
                create_service(SERVER_CONFIG) as service,
            ):
                handler.append(service.stop_running)

                await service.run()
    case "client":

        async def serve() -> None:
            async with (
                handle_signals() as handler,
                serve_metrics(CLIENT_CONFIG.metrics),
                create_service(CLIENT_CONFIG) as service,
            ):
                handler.append(service.stop_running)

                await service.run()
    case _:

        async def serve() -> None:
            pass


init_logging("debug")
asyncio.run(serve())
