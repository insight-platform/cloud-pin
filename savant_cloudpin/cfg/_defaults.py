from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    HealthConfig,
    MetricsConfig,
    OTLPMetricConfig,
    PrometheusConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    WriterConfig,
)

DEFAULT_LOAD_CONFIG = dict(
    config="./cloudpin.yml",
    mode="client",
)

DEFAULT_SOURCE_CONFIG = ReaderConfig(
    url="???",
)
DEFAULT_SINK_CONFIG = WriterConfig(
    url="???",
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
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
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
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
    health=DEFAULT_HEALTH_CONFIG,
    metrics=DEFAULT_METRICS_CONFIG,
)
