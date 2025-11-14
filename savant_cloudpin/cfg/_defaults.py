from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    HealthConfig,
    MetricsConfig,
    OTLPMetricConfig,
    PrometheusConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    ZMQReaderConfig,
    ZMQWriterConfig,
)

DEFAULT_LOAD_CONFIG = dict(
    config="./cloudpin.yml",
    mode="client",
)

DEFAULT_ZMQ_SRC_CONFIG = ZMQReaderConfig(
    endpoint="???",
)
DEFAULT_ZMQ_SINK_CONFIG = ZMQWriterConfig(
    endpoint="???",
)

DEFAULT_HEALTH_CONFIG = HealthConfig(endpoint="???")

DEFAULT_METRICS_CONFIG = MetricsConfig(
    otlp=OTLPMetricConfig(endpoint="???"),
    prometheus=PrometheusConfig(endpoint="???"),
)

DEFAULT_CLIENT_CONFIG = ClientServiceConfig(
    websockets=ClientWSConfig(
        endpoint="???",
        api_key="???",
        ssl=ClientSSLConfig(),
    ),
    zmq_src=DEFAULT_ZMQ_SRC_CONFIG,
    zmq_sink=DEFAULT_ZMQ_SINK_CONFIG,
    health=DEFAULT_HEALTH_CONFIG,
    metrics=DEFAULT_METRICS_CONFIG,
)

DEFAULT_SERVER_CONFIG = ServerServiceConfig(
    websockets=ServerWSConfig(
        endpoint="???",
        api_key="???",
        ssl=ServerSSLConfig(
            cert_file="???",
            key_file="???",
        ),
    ),
    zmq_src=DEFAULT_ZMQ_SRC_CONFIG,
    zmq_sink=DEFAULT_ZMQ_SINK_CONFIG,
    health=DEFAULT_HEALTH_CONFIG,
    metrics=DEFAULT_METRICS_CONFIG,
)
