from dataclasses import dataclass, field, replace
from typing import Protocol, Self

from savant_rs import zmq

from savant_cloudpin.cfg._utils import ALT_ENV, to_map_config

SENSITIVE_KEYS = ("api_key",)


@dataclass
class ZMQReaderConfig:
    endpoint: str
    results_queue_size: int = 100
    receive_timeout: int | None = None
    receive_hwm: int | None = None
    topic_prefix_spec: str | None = None
    routing_ids_cache_size: int | None = None
    fix_ipc_permissions: str | None = None
    source_blacklist_size: int | None = None
    source_blacklist_ttl: int | None = None

    def as_router(self) -> Self:
        return replace(self, endpoint="router+" + self.endpoint.split("+")[-1])

    def to_args(self) -> tuple[zmq.ReaderConfig, int]:
        cfg = zmq.ReaderConfigBuilder(self.endpoint)
        cfg.with_map_config(
            to_map_config(self, excluded=("endpoint", "results_queue_size"))
        )
        return cfg.build(), self.results_queue_size


@dataclass
class ZMQWriterConfig:
    endpoint: str
    max_inflight_messages: int = 100
    send_timeout: int | None = None
    send_retries: int | None = None
    send_hwm: int | None = None
    receive_timeout: int | None = None
    receive_retries: int | None = None
    receive_hwm: int | None = None
    fix_ipc_permissions: str | None = None

    def as_dealer(self) -> Self:
        return replace(self, endpoint="dealer+" + self.endpoint.split("+")[-1])

    def to_args(self) -> tuple[zmq.WriterConfig, int]:
        cfg = zmq.WriterConfigBuilder(self.endpoint)
        cfg.with_map_config(
            to_map_config(self, excluded=("endpoint", "max_inflight_messages"))
        )
        return cfg.build(), self.max_inflight_messages


@dataclass
class ServerSSLConfig:
    cert_file: str
    key_file: str
    ca_file: str | None = None
    client_cert_required: bool = True


@dataclass
class ClientSSLConfig:
    cert_file: str | None = None
    key_file: str | None = None
    ca_file: str | None = None
    check_hostname: bool = True
    insecure: bool = False


@dataclass
class ServerWSConfig:
    endpoint: str
    api_key: str
    ssl: ServerSSLConfig | None = None


@dataclass
class ClientWSConfig:
    endpoint: str
    api_key: str
    ssl: ClientSSLConfig
    reconnect_timeout: float = 2.0


@dataclass
class HealthConfig:
    endpoint: str


@dataclass
class OTLPMetricConfig:
    endpoint: str = field(metadata={ALT_ENV: "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"})
    export_timeout: float = 3.0
    custom_path: bool = False


@dataclass
class PrometheusConfig:
    endpoint: str
    custom_path: bool = False


@dataclass
class HistogramBoundaries:
    delay: list[float] | None = field(
        default_factory=lambda: [0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.1]
    )
    left_zmq_capacity: list[float] | None = None
    consumed_zmq_capacity: list[float] | None = None
    left_ws_reading_capacity: list[float] | None = None
    consumed_ws_reading_capacity: list[float] | None = None
    message_size: list[float] | None = None


@dataclass
class MetricsConfig:
    prometheus: PrometheusConfig | None = None
    otlp: OTLPMetricConfig | None = None
    histogram_boundaries: HistogramBoundaries = field(
        default_factory=HistogramBoundaries
    )


class BaseServiceConfig(Protocol):
    zmq_src: ZMQReaderConfig
    zmq_sink: ZMQWriterConfig
    io_timeout: float
    loglevel: str | None = field(default="warning", metadata={ALT_ENV: "LOGLEVEL"})
    health: HealthConfig | None
    metrics: MetricsConfig | None


@dataclass
class ServerServiceConfig(BaseServiceConfig):
    websockets: ServerWSConfig
    zmq_src: ZMQReaderConfig
    zmq_sink: ZMQWriterConfig
    io_timeout: float = 0.1
    loglevel: str | None = field(default="warning", metadata={ALT_ENV: "LOGLEVEL"})
    health: HealthConfig | None = None
    metrics: MetricsConfig | None = None


@dataclass
class ClientServiceConfig(BaseServiceConfig):
    websockets: ClientWSConfig
    zmq_src: ZMQReaderConfig
    zmq_sink: ZMQWriterConfig
    io_timeout: float = 0.1
    loglevel: str | None = field(default="warning", metadata={ALT_ENV: "LOGLEVEL"})
    health: HealthConfig | None = None
    metrics: MetricsConfig | None = None
