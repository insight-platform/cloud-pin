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
)
from savant_cloudpin.cfg._models import (
    ClientServiceConfig,
    ClientSSLConfig,
    ClientWSConfig,
    ReaderConfig,
    ServerServiceConfig,
    ServerSSLConfig,
    ServerWSConfig,
    SSLCertConfig,
    SSLCertKeyConfig,
    WriterConfig,
)

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
        structured_config_mode=SCMode.DICT_CONFIG,
        resolve=True,
    )
    assert isinstance(config, DictConfig)

    ssl_config = config.websockets.ssl
    if service_cls == ServerServiceConfig:
        ssl_config.server = SSLCertKeyConfig(**ssl_config.server)
        ssl_config.client = SSLCertConfig(**ssl_config.client)
        config.websockets.ssl = ServerSSLConfig(**ssl_config)
        ws_config = ServerWSConfig(**config.websockets)
    else:
        ssl_config.server = SSLCertConfig(**ssl_config.server)
        ssl_config.client = SSLCertKeyConfig(**ssl_config.client)
        config.websockets.ssl = ClientSSLConfig(**ssl_config)
        ws_config = ClientWSConfig(**config.websockets)

    config = service_cls(
        websockets=ws_config,
        io_timeout=config.io_timeout,
        source=ReaderConfig(**config.source),
        sink=WriterConfig(**config.sink),
    )
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

    assert isinstance(yaml_config, DictConfig)

    load_config = OmegaConf.merge(DEFAULT_LOAD_CONFIG, yaml_config, cli_config)

    cli_config.pop("config", None)
    cli_config.pop("mode", None)
    yaml_config.pop("mode", None)

    match load_config.mode:
        case "server":
            config = OmegaConf.merge(DEFAULT_SERVER_CONFIG, yaml_config, cli_config)
            return validated_dataclass(config, ServerServiceConfig)
        case "client" | None:
            config = OmegaConf.merge(DEFAULT_CLIENT_CONFIG, yaml_config, cli_config)
            return validated_dataclass(config, ClientServiceConfig)
        case _:
            raise ValueError("Invalid service mode")
