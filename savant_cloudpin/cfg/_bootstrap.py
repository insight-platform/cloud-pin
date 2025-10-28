import os.path
import re
from typing import Any

from omegaconf import OmegaConf
from omegaconf.base import SCMode
from omegaconf.dictconfig import DictConfig

from savant_cloudpin.cfg import _utils as utils
from savant_cloudpin.cfg._defaults import (
    DEFAULT_CLIENT_CONFIG,
    DEFAULT_LOAD_CONFIG,
    DEFAULT_SERVER_CONFIG,
)
from savant_cloudpin.cfg._models import ClientServiceConfig, ServerServiceConfig

SOURCE_URL_ALLOWED_REGEX = (
    r"(router[+])?(bind|connect):(tcp://[^: \t\n\r\f\v]+:\d+|ipc:///.+)"
)
SINK_URL_ALLOWED_REGEX = (
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

    if not re.fullmatch(SOURCE_URL_ALLOWED_REGEX, config.source.url):
        raise ValueError(f"Invalid source.url '{config.source.url}'")
    if not re.fullmatch(SINK_URL_ALLOWED_REGEX, config.sink.url):
        raise ValueError(f"Invalid sink.url '{config.sink.url}'")
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

    ssl = "websockets" in cfg and "ssl" in cfg.websockets
    ssl = cfg.websockets.ssl if ssl else {}

    cfg = OmegaConf.merge(default_cfg, cfg)
    assert isinstance(cfg, DictConfig)
    if not any(val is not None for val in ssl.values()):
        cfg.websockets.ssl = None
    return cfg


def load_config(
    args_list: list[str] | None = None,
) -> ClientServiceConfig | ServerServiceConfig:
    cli_cfg = OmegaConf.from_cli(args_list)
    env_cfg = utils.as_value_dict(utils.env_override(DEFAULT_LOAD_CONFIG))
    cfg = OmegaConf.merge(env_cfg, cli_cfg)

    yml_exists = cfg.config and os.path.exists(cfg.config)
    yml_cfg = OmegaConf.load(cfg.config) if yml_exists else OmegaConf.create({})

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
