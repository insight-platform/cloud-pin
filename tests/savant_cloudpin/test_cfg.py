import os
import unittest.mock
from unittest.mock import Mock

import pytest
from faker import Faker

from savant_cloudpin.cfg import ClientServiceConfig, ServerServiceConfig, load_config

fake = Faker()


def fake_zmq_url() -> str:
    dir = fake.random_element(["bind", "connect"])
    schema = fake.random_element(["ipc", "tcp"])
    if schema == "tcp":
        url = fake.url(["tcp"]).rstrip("/")
        port = fake.port_number()
        return f"{dir}:{url}:{port}"
    else:
        path = fake.file_path()
        return f"{dir}:ipc://{path}"


@pytest.fixture(scope="function")
def some_cli_config() -> dict[str, str]:
    mode = fake.random_element(["server", "client"])
    ssl = fake.boolean()

    match mode:
        case "server" if ssl:
            return {
                "mode": "server",
                "websockets.server_url": fake.uri(["wss", "ws"]),
                "websockets.api_key": fake.passport_number(),
                "websockets.ssl.cert_file": fake.file_path(),
                "websockets.ssl.key_file": fake.file_path(),
                "source.url": fake_zmq_url(),
                "sink.url": fake_zmq_url(),
            }
        case "server" if not ssl:
            return {
                "mode": "server",
                "websockets.server_url": fake.uri(["wss", "ws"]),
                "websockets.api_key": fake.passport_number(),
                "source.url": fake_zmq_url(),
                "sink.url": fake_zmq_url(),
            }
        case "client":
            return {
                "mode": "client",
                "websockets.server_url": fake.uri(["wss", "ws"]),
                "websockets.api_key": fake.passport_number(),
                "websockets.ssl.cert_file": fake.file_path(),
                "websockets.ssl.key_file": fake.file_path(),
                "source.url": fake_zmq_url(),
                "sink.url": fake_zmq_url(),
            }
        case _:
            return {}


@pytest.fixture(
    params=[
        ("router+bind:tcp://1.2.3.4:1500", "dealer+bind:tcp://1.2.3.4:1501"),
        ("bind:tcp://1.2.3.4:1500", "bind:tcp://1.2.3.4:1501"),
        ("router+connect:tcp://1.2.3.4:1500", "dealer+connect:tcp://1.2.3.4:1501"),
        ("connect:tcp://1.2.3.4:1500", "connect:tcp://1.2.3.4:1501"),
        ("router+bind:ipc:///file/path1", "dealer+bind:ipc:///file/path2"),
        ("bind:ipc:///file/sys/path", "bind:ipc:///file/sys/another-path"),
        ("router+connect:ipc:///file/path1", "dealer+connect:ipc:///file/path2"),
        ("connect:ipc:///file/sys/path", "connect:ipc:///file/sys/another-path"),
    ],
    ids="|".join,
)
def valid_urls(request: pytest.FixtureRequest) -> tuple[str, str]:
    return request.param


@pytest.fixture(
    params=[
        ("dealer+bind:tcp://1.2.3.4:1500", "dealer+bind:tcp://1.2.3.4:1501"),
        ("bind:tcp://1.2.3.4:1500", "router+bind:tcp://1.2.3.4:1501"),
        ("dealer+bind:ipc:///file/path1", "dealer+bind:ipc:///file/path2"),
        ("bind:ipc:///file/path1", "router+bind:ipc:///file/path2"),
        ("http://1.2.3.4:1500", "bind:tcp://1.2.3.4:1501"),
        ("bind:tcp://1.2.3.4:1500", "http://1.2.3.4:1501"),
    ],
    ids=" | ".join,
)
def invalid_urls(request: pytest.FixtureRequest) -> tuple[str, str]:
    return request.param


def test_load_config_when_valid_urls(
    valid_urls: tuple[str, str], some_cli_config: dict[str, str]
) -> None:
    source_url, sink_url = valid_urls
    cli_config = some_cli_config.copy()
    cli_config.update({"source.url": source_url, "sink.url": sink_url})
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    result = load_config(cli_args)

    assert isinstance(result, (ServerServiceConfig, ClientServiceConfig))
    assert result.source.url == source_url
    assert result.sink.url == sink_url


def test_load_config_when_invalid_urls(
    invalid_urls: tuple[str, str], some_cli_config: dict[str, str]
) -> None:
    source_url, sink_url = invalid_urls
    cli_config = some_cli_config.copy()
    cli_config.update({"source.url": source_url, "sink.url": sink_url})
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    with pytest.raises(ValueError):
        load_config(cli_args)


def test_load_config_with_environ_var(some_cli_config: dict[str, str]) -> None:
    server_url = fake.uri(["wss", "ws"])
    environ_vars = {"CLOUDPIN_WEBSOCKETS_SERVER_URL": server_url}
    cli_config = some_cli_config.copy()
    del cli_config["websockets.server_url"]
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    with unittest.mock.patch.dict(os.environ, environ_vars):
        result = load_config(cli_args)

    assert isinstance(result, (ServerServiceConfig, ClientServiceConfig))
    assert result.websockets.server_url == server_url


def test_load_config_with_file(some_cli_config: dict[str, str]) -> None:
    server_url = fake.uri(["wss", "ws"])
    config_path = f"/tmp{fake.file_path(extension='yml')}"
    file_mock = unittest.mock.mock_open(
        read_data=(f"websockets:\n  server_url: {server_url}"),
    )
    path_exists_mock = Mock()
    path_exists_mock.return_value = True
    cli_config = some_cli_config.copy()
    del cli_config["websockets.server_url"]
    cli_config["config"] = config_path
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    with unittest.mock.patch("os.path.exists", path_exists_mock):
        with unittest.mock.patch("io.open", file_mock):
            result = load_config(cli_args)

    assert isinstance(result, (ServerServiceConfig, ClientServiceConfig))
    assert result.websockets.server_url == server_url
    assert path_exists_mock.call_count == 1
    assert path_exists_mock.call_args == unittest.mock.call(config_path)


def test_load_config_that_cli_override_env(some_cli_config: dict[str, str]) -> None:
    env_server_url = fake.uri(["wss", "ws"])
    cli_server_url = fake.uri(["wss", "ws"])
    environ_vars = {"CLOUDPIN_WEBSOCKETS_SERVER_URL": env_server_url}
    cli_config = some_cli_config.copy()
    cli_config["websockets.server_url"] = cli_server_url
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    with unittest.mock.patch.dict(os.environ, environ_vars):
        result = load_config(cli_args)

    assert isinstance(result, (ServerServiceConfig, ClientServiceConfig))
    assert result.websockets.server_url == cli_server_url


def test_load_config_that_env_override_file(some_cli_config: dict[str, str]) -> None:
    env_server_url = fake.uri(["wss", "ws"])
    file_server_url = fake.uri(["wss", "ws"])
    environ_vars = {"CLOUDPIN_WEBSOCKETS_SERVER_URL": env_server_url}
    config_path = f"/tmp{fake.file_path(extension='yml')}"
    file_mock = unittest.mock.mock_open(
        read_data=(f"websockets:\n  server_url: {file_server_url}"),
    )
    path_exists_mock = Mock()
    path_exists_mock.return_value = True
    cli_config = some_cli_config.copy()
    del cli_config["websockets.server_url"]
    cli_config["config"] = config_path
    cli_args = ["=".join(arg) for arg in cli_config.items()]

    with (
        unittest.mock.patch.dict(os.environ, environ_vars),
        unittest.mock.patch("os.path.exists", path_exists_mock),
        unittest.mock.patch("io.open", file_mock),
    ):
        result = load_config(cli_args)

    assert isinstance(result, (ServerServiceConfig, ClientServiceConfig))
    assert result.websockets.server_url == env_server_url
    assert path_exists_mock.call_count == 1
    assert path_exists_mock.call_args == unittest.mock.call(config_path)
