import copy
import os.path
import re
from collections.abc import Sequence
from typing import Any

from omegaconf import DictConfig, ListConfig, OmegaConf, SCMode

from savant_cloudpin.cfg import _utils as utils
from savant_cloudpin.cfg._defaults import (
    DEFAULT_CLIENT_CONFIG,
    DEFAULT_LOAD_CONFIG,
    DEFAULT_SERVER_CONFIG,
)
from savant_cloudpin.cfg._models import ClientServiceConfig, ServerServiceConfig

ZMQ_SRC_ENDPOINT_ALLOWED_REGEX = (
    r"(router[+])?(bind|connect):(tcp://[^: \t\n\r\f\v]+:\d+|ipc:///.+)"
)
ZMQ_SINK_EDNPOINT_ALLOWED_REGEX = (
    r"(dealer[+])?(bind|connect):(tcp://[^: \t\n\r\f\v]+:\d+|ipc:///.+)"
)


def validated_dataclass[T: ClientServiceConfig | ServerServiceConfig](
    config: Any, service_cls: type[T]
) -> T:
    config = OmegaConf.to_container(
        config,
        throw_on_missing=True,
        structured_config_mode=SCMode.INSTANTIATE,
        resolve=True,
    )
    assert isinstance(config, service_cls)

    if not re.fullmatch(ZMQ_SRC_ENDPOINT_ALLOWED_REGEX, config.zmq_src.endpoint):
        raise ValueError(f"Invalid source.url '{config.zmq_src.endpoint}'")
    if not re.fullmatch(ZMQ_SINK_EDNPOINT_ALLOWED_REGEX, config.zmq_sink.endpoint):
        raise ValueError(f"Invalid sink.url '{config.zmq_sink.endpoint}'")
    return config


def merge_env_config(
    defaults: ServerServiceConfig | ClientServiceConfig,
    yml_cfg: DictConfig | dict,
    cli_cfg: DictConfig | dict,
) -> DictConfig:
    default_cfg = OmegaConf.structured(defaults)
    env_cfg = utils.as_value_dict(utils.env_override(defaults, "null"))
    env_cfg = OmegaConf.to_container(OmegaConf.create(env_cfg), resolve=True)
    assert isinstance(env_cfg, dict)
    env_cfg = utils.drop_none_values(env_cfg)
    cfg = OmegaConf.merge(yml_cfg, env_cfg, cli_cfg)

    assert isinstance(cfg, DictConfig)
    cfg.websockets = utils.drop_none_values(cfg.get("websockets", {}))
    ssl = cfg.websockets.get("ssl", None)
    health = utils.drop_none_values(cfg.get("health", {}))
    metrics = utils.drop_none_values(cfg.get("metrics", {}))
    otlp = metrics.get("otlp", {})
    prometheus = metrics.get("prometheus", {})

    cfg = OmegaConf.merge(default_cfg, cfg)
    assert isinstance(cfg, DictConfig)
    if not ssl:
        cfg.websockets["ssl"] = None
    if not health:
        cfg.health = None
    if not metrics:
        cfg.metrics = None
    else:
        if not otlp:
            cfg.metrics.otlp = None
        if not prometheus:
            cfg.metrics.prometheus = None
    return cfg


def join_log_spec(cfg: DictConfig | ListConfig) -> None:
    if not isinstance(cfg, DictConfig) or "loglevel" not in cfg:
        return
    if not isinstance(cfg.loglevel, (DictConfig, dict)):
        return
    cfg.loglevel = ",".join(f"{k}={v}" for k, v in cfg.loglevel.items())


def load_config(
    args_list: list[str] | None = None,
) -> ClientServiceConfig | ServerServiceConfig:
    cli_cfg = OmegaConf.from_cli(args_list)
    env_cfg = utils.env_override(DEFAULT_LOAD_CONFIG)
    cfg = OmegaConf.merge(env_cfg, cli_cfg)

    yml_exists = cfg.config and os.path.exists(cfg.config)
    yml_cfg = OmegaConf.load(cfg.config) if yml_exists else OmegaConf.create({})
    join_log_spec(yml_cfg)

    cfg = OmegaConf.merge(yml_cfg, env_cfg, cli_cfg)
    assert isinstance(cfg, DictConfig) and isinstance(yml_cfg, DictConfig)

    cli_cfg.pop("config", None)
    cli_cfg.pop("mode", None)
    yml_cfg.pop("mode", None)

    match cfg.mode:
        case "server":
            cfg = merge_env_config(DEFAULT_SERVER_CONFIG, yml_cfg, cli_cfg)
            return validated_dataclass(cfg, ServerServiceConfig)
        case "client" | None:
            cfg = merge_env_config(DEFAULT_CLIENT_CONFIG, yml_cfg, cli_cfg)
            return validated_dataclass(cfg, ClientServiceConfig)
        case _:
            raise ValueError("Invalid service mode")


def dump_to_yaml(
    config: ClientServiceConfig | ServerServiceConfig, scrape_keys: Sequence[str] = ()
) -> str:
    if scrape_keys:
        config = copy.deepcopy(config)
        utils.scrape_sensitive_keys(config, scrape_keys)

    mode = "server" if isinstance(config, ServerServiceConfig) else "client"
    summary = OmegaConf.to_container(
        OmegaConf.structured(config), structured_config_mode=SCMode.DICT
    )
    summary = OmegaConf.merge(dict(mode=mode), summary)
    return OmegaConf.to_yaml(summary)
