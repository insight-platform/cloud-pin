import dataclasses
import re
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from omegaconf.base import SCMode
from omegaconf.dictconfig import DictConfig

from savant_cloudpin.cfg._defaults import (
    DEFAULT_CLIENT_CONFIG,
    DEFAULT_LOAD_CONFIG,
    DEFAULT_SERVER_CONFIG,
    NULL_SSL_SERVER_CONFIG,
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


def load_config(
    args_list: list[str] | None = None,
) -> ClientServiceConfig | ServerServiceConfig:
    cli_config = OmegaConf.from_cli(args_list)
    load_config = OmegaConf.merge(DEFAULT_LOAD_CONFIG, cli_config)

    if load_config.config and Path(load_config.config).exists():
        yaml_config = OmegaConf.load(load_config.config)
    else:
        yaml_config = OmegaConf.create()

    config = OmegaConf.merge(DEFAULT_LOAD_CONFIG, yaml_config, cli_config)
    assert isinstance(config, DictConfig)

    config.pop("config", None)
    match config.pop("mode", None):
        case "server":
            ssl_config = OmegaConf.merge(
                dataclasses.asdict(NULL_SSL_SERVER_CONFIG), config
            ).websockets.ssl
            assert isinstance(ssl_config, DictConfig)
            missing_ssl = all(v is None for _, v in ssl_config.items())

            config = OmegaConf.merge(DEFAULT_SERVER_CONFIG, config)
            if missing_ssl:
                config.websockets.ssl = None
            return validated_dataclass(config, ServerServiceConfig)
        case "client" | None:
            config = OmegaConf.merge(DEFAULT_CLIENT_CONFIG, config)
            return validated_dataclass(config, ClientServiceConfig)
        case _:
            raise ValueError("Invalid service mode")
