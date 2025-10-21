import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Self

from omegaconf import SI, OmegaConf
from omegaconf.base import SCMode
from omegaconf.dictconfig import DictConfig


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


@dataclass
class WriterConfig:
    max_infight_messages: int
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


@dataclass
class ServiceConfig:
    mode: str
    source: ReaderConfig
    sink: WriterConfig


@dataclass
class CliServiceConfig(ServiceConfig):
    config: str


_SOURCE_URL_ALLOWED_REGEX = (
    r"(router[+])?(bind|connect):(tcp://[^: \t\n\r\f\v]+:\d+|ipc:///.+)"
)
_SINK_URL_ALLOWED_REGEX = (
    r"(dealer[+])?(bind|connect):(tcp://[^: \t\n\r\f\v]+:\d+|ipc:///.+)"
)
_DEFAULT_SOURCE_CONFIG = ReaderConfig(
    results_queue_size=SI("${oc.env:CLOUDPIN_SOURCE_RESULTS_QUEUE_SIZE,100}"),
    url="${oc.env:CLOUDPIN_SOURCE_URL,???}",
    receive_timeout=SI("${oc.env:CLOUDPIN_SOURCE_RECEIVE_TIMEOUT,null}"),
    receive_hwm=SI("${oc.env:CLOUDPIN_SOURCE_RECEIVE_HWM,null}"),
    topic_prefix_spec="${oc.env:CLOUDPIN_SOURCE_TOPIC_PREFIX_SPEC,null}",
    routing_ids_cache_size=SI("${oc.env:CLOUDPIN_ROUTING_IDS_CACHE_SIZE,null}"),
    fix_ipc_permissions=("${oc.env:CLOUDPIN_SOURCE_FIX_IPC_PERMISSIONS,null}"),
    source_blacklist_size=SI("${oc.env:CLOUDPIN_SOURCE_SOURCE_BLACKLIST_SIZE,null}"),
    source_blacklist_ttl=SI("${oc.env:CLOUDPIN_SOURCE_SOURCE_BLACKLIST_TTL,null}"),
)
_DEFAULT_SINK_CONFIG = WriterConfig(
    max_infight_messages=SI("${oc.env:CLOUDPIN_SINK_MAX_INFIGHT_MESSAGES,100}"),
    url="${oc.env:CLOUDPIN_SINK_URL,???}",
    send_timeout=SI("${oc.env:CLOUDPIN_SINK_SEND_TIMEOUT,null}"),
    send_retries=SI("${oc.env:CLOUDPIN_SINK_SEND_RETRIES,null}"),
    send_hwm=SI("${oc.env:CLOUDPIN_SINK_SEND_HWM,null}"),
    receive_timeout=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_TIMEOUT,null}"),
    receive_retries=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_RETRIES,null}"),
    receive_hwm=SI("${oc.env:CLOUDPIN_SINK_RECEIVE_HWM,null}"),
    fix_ipc_permissions=SI("${oc.env:CLOUDPIN_SINK_FIX_IPC_PERMISSIONS,null}"),
)
_DEFAULT_SERVICE_CONFIG = CliServiceConfig(
    config="{oc.env:CLOUDPIN_CONFIG_FILE,./cloudpin.yml}",
    mode="${oc.env:CLOUDPIN_MODE,client}",
    source=OmegaConf.structured(
        _DEFAULT_SOURCE_CONFIG, flags={"throw_on_missing": True}
    ),
    sink=OmegaConf.structured(_DEFAULT_SINK_CONFIG, flags={"throw_on_missing": True}),
)


def _to_validated(config: Any) -> ServiceConfig:
    config = OmegaConf.to_container(
        config,
        throw_on_missing=True,
        structured_config_mode=SCMode.DICT_CONFIG,
        resolve=True,
    )
    assert isinstance(config, DictConfig)

    config = ServiceConfig(
        mode=config["mode"],
        source=ReaderConfig(**config["source"]),
        sink=WriterConfig(**config["sink"]),
    )
    if config.mode not in ("client", "server"):
        raise ValueError(f"Invalid mode '{config.mode}'")
    if not re.fullmatch(_SOURCE_URL_ALLOWED_REGEX, config.source.url):
        raise ValueError(f"Invalid source.url '{config.source.url}'")
    if not re.fullmatch(_SINK_URL_ALLOWED_REGEX, config.sink.url):
        raise ValueError(f"Invalid sink.url '{config.sink.url}'")
    return config


def load_config(args_list: list[str] | None = None) -> ServiceConfig:
    config = OmegaConf.merge({}, _DEFAULT_SERVICE_CONFIG, OmegaConf.from_cli(args_list))
    assert isinstance(config, DictConfig)

    config_file = Path(config["config"]) if "config" in config else None
    if config_file and config_file.exists():
        config = OmegaConf.merge(
            {},
            _DEFAULT_SERVICE_CONFIG,
            OmegaConf.load(config_file),
            OmegaConf.from_cli(),
        )

    return _to_validated(config)
