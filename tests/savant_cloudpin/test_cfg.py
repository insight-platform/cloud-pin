from savant_cloudpin.cfg import load_config
import pytest
from faker import Faker


fake = Faker()

DUMMY_WEBSOCKET_CLI_CONFIG = [
    "websockets.server_url=wss://localhost",
    "websockets.api_key=secret_key",
]


@pytest.fixture
def dummy_websocket_server_cli_config() -> list[str]:
    return [
        r"mode=server",
        f"websockets.server_url={fake.uri(['wss', 'ws'])}",
        f"websockets.api_key={fake.passport_number()}",
        r"websockets.disable_ssl=true",
    ]


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
    ids=lambda pair: " | ".join(pair),
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
    ids=lambda pair: " | ".join(pair),
)
def invalid_urls(request: pytest.FixtureRequest) -> tuple[str, str]:
    return request.param


def test_load_config_when_valid_urls(
    dummy_websocket_server_cli_config: list[str], valid_urls: tuple[str, str]
) -> None:
    source_url, sink_url = valid_urls

    load_config(
        [
            *dummy_websocket_server_cli_config,
            f"source.url={source_url}",
            f"sink.url={sink_url}",
        ]
    )


def test_load_config_when_invalid_urls(
    dummy_websocket_server_cli_config: list[str], invalid_urls: tuple[str, str]
) -> None:
    source_url, sink_url = invalid_urls

    with pytest.raises(ValueError):
        load_config(
            [
                *dummy_websocket_server_cli_config,
                f"source.url={source_url}",
                f"sink.url={sink_url}",
            ]
        )
