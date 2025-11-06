from collections.abc import Generator

import pytest
from savant_rs.zmq import ReaderConfigBuilder, WriterConfigBuilder

from savant_cloudpin.cfg import ReaderConfig, WriterConfig
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.connections import ConnectDir, SocketType, opposite_dir_url
from tests.helpers.ports import PortPool


@pytest.fixture
def client_sink_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"bind:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def server_sink_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"connect:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def var_sink_url(
    port_pool: PortPool, connect_dir1: ConnectDir, socket_type: SocketType
) -> Generator[str]:
    with port_pool.lease() as port:
        if socket_type == "tcp":
            yield f"{connect_dir1}:tcp://127.0.0.1:{port}"
        else:
            yield f"{connect_dir1}:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def client_reader(client_sink_url: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(client_sink_url)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def server_reader(server_sink_url: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(server_sink_url)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def var_reader(var_sink_url: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(var_sink_url)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def client_sink_config(client_sink_url: str) -> WriterConfig:
    return WriterConfig(
        max_inflight_messages=1000,
        url=client_sink_url,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def server_sink_config(server_sink_url: str) -> WriterConfig:
    return WriterConfig(
        max_inflight_messages=1000,
        url=server_sink_url,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def var_sink_config(var_sink_url: str) -> WriterConfig:
    return WriterConfig(
        max_inflight_messages=1000,
        url=var_sink_url,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def client_source_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"bind:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def server_source_url(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"connect:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def var_source_url(
    port_pool: PortPool, connect_dir2: ConnectDir, socket_type: SocketType
) -> Generator[str]:
    with port_pool.lease() as port:
        if socket_type == "tcp":
            yield f"{connect_dir2}:tcp://127.0.0.1:{port}"
        else:
            yield f"{connect_dir2}:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def client_writer(client_source_url: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(client_source_url)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def server_writer(server_source_url: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(server_source_url)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def var_writer(var_source_url: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(var_source_url)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def client_source_config(client_source_url: str) -> ReaderConfig:
    return ReaderConfig(
        results_queue_size=1000, url=client_source_url, receive_timeout=1000
    )


@pytest.fixture
def server_source_config(server_source_url: str) -> ReaderConfig:
    return ReaderConfig(
        results_queue_size=1000, url=server_source_url, receive_timeout=1000
    )


@pytest.fixture
def var_source_config(var_source_url: str) -> ReaderConfig:
    return ReaderConfig(
        results_queue_size=1000, url=var_source_url, receive_timeout=1000
    )
