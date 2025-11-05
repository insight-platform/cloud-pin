from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    ObservabilityConfig,
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

DEFAULT_OBSERVABILITY_CONFIG = ObservabilityConfig(
    log_spec="${oc.env:LOGLEVEL,warning}"
)

DEFAULT_CLIENT_CONFIG = ClientServiceConfig(
    websockets=ClientWSConfig(
        server_url="???",
        api_key="???",
        ssl=ClientSSLConfig(
            ca_file=None,
            cert_file="???",
            key_file="???",
            check_hostname=False,
        ),
    ),
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
    observability=DEFAULT_OBSERVABILITY_CONFIG,
)

DEFAULT_SERVER_CONFIG = ServerServiceConfig(
    websockets=ServerWSConfig(
        server_url="???",
        api_key="???",
        ssl=ServerSSLConfig(
            ca_file=None,
            cert_file="???",
            key_file="???",
            client_cert_required=True,
        ),
    ),
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
    observability=DEFAULT_OBSERVABILITY_CONFIG,
)
