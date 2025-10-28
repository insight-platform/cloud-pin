from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    LoadConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    WriterConfig,
)

DEFAULT_SOURCE_CONFIG = ReaderConfig(
    results_queue_size=100,
    url="???",
)
DEFAULT_SINK_CONFIG = WriterConfig(
    max_inflight_messages=100,
    url="???",
)


DEFAULT_LOAD_CONFIG = LoadConfig(
    config="./cloudpin.yml",
    mode="client",
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
    io_timeout=0.1,
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
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
    io_timeout=0.1,
    source=DEFAULT_SOURCE_CONFIG,
    sink=DEFAULT_SINK_CONFIG,
)
