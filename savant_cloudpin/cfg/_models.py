from dataclasses import dataclass, replace
from typing import Self

from savant_rs import zmq

from savant_cloudpin.cfg._utils import to_map_config


@dataclass
class ReaderConfig:
    results_queue_size: int
    url: str
    receive_timeout: int | None = None
    receive_hwm: int | None = None
    topic_prefix_spec: str | None = None
    routing_ids_cache_size: int | None = None
    fix_ipc_permissions: str | None = None
    source_blacklist_size: int | None = None
    source_blacklist_ttl: int | None = None

    def as_router(self) -> Self:
        return replace(self, url="router+" + self.url.split("+")[-1])

    def to_args(self) -> tuple[zmq.ReaderConfig, int]:
        cfg = zmq.ReaderConfigBuilder(self.url)
        cfg.with_map_config(to_map_config(self, excluded=("url", "results_queue_size")))
        return cfg.build(), self.results_queue_size


@dataclass
class WriterConfig:
    max_inflight_messages: int
    url: str
    send_timeout: int | None = None
    send_retries: int | None = None
    send_hwm: int | None = None
    receive_timeout: int | None = None
    receive_retries: int | None = None
    receive_hwm: int | None = None
    fix_ipc_permissions: str | None = None

    def as_dealer(self) -> Self:
        return replace(self, url="dealer+" + self.url.split("+")[-1])

    def to_args(self) -> tuple[zmq.WriterConfig, int]:
        cfg = zmq.WriterConfigBuilder(self.url)
        cfg.with_map_config(
            to_map_config(self, excluded=("url", "max_inflight_messages"))
        )
        return cfg.build(), self.max_inflight_messages


@dataclass
class ServerSSLConfig:
    ca_file: str | None
    cert_file: str
    key_file: str
    client_cert_required: bool


@dataclass
class ClientSSLConfig:
    ca_file: str | None
    cert_file: str | None
    key_file: str | None
    check_hostname: bool


@dataclass
class ServerWSConfig:
    server_url: str
    api_key: str
    ssl: ServerSSLConfig | None = None


@dataclass
class ClientWSConfig:
    server_url: str
    api_key: str
    ssl: ClientSSLConfig


@dataclass
class BaseServiceConfig:
    io_timeout: float
    source: ReaderConfig
    sink: WriterConfig


@dataclass
class ServerServiceConfig(BaseServiceConfig):
    websockets: ServerWSConfig


@dataclass
class ClientServiceConfig(BaseServiceConfig):
    websockets: ClientWSConfig


@dataclass
class LoadConfig:
    config: str | None
    mode: str | None
