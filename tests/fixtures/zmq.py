from collections.abc import Generator

import pytest
from savant_rs.zmq import ReaderConfigBuilder, WriterConfigBuilder

from savant_cloudpin.cfg import ZMQReaderConfig, ZMQWriterConfig
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests.helpers.connections import ConnectDir, SocketType, opposite_dir_url
from tests.helpers.ports import PortPool


@pytest.fixture
def client_zmq_sink_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"bind:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def server_zmq_sink_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"connect:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def var_zmq_sink_endpoint(
    port_pool: PortPool, connect_dir1: ConnectDir, socket_type: SocketType
) -> Generator[str]:
    with port_pool.lease() as port:
        if socket_type == "tcp":
            yield f"{connect_dir1}:tcp://127.0.0.1:{port}"
        else:
            yield f"{connect_dir1}:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def client_zmq_reader(client_zmq_sink_endpoint: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(client_zmq_sink_endpoint)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def server_zmq_reader(server_zmq_sink_endpoint: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(server_zmq_sink_endpoint)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def var_zmq_reader(var_zmq_sink_endpoint: str) -> Generator[NonBlockingReader]:
    cfg = ReaderConfigBuilder(f"router+{opposite_dir_url(var_zmq_sink_endpoint)}")
    cfg.with_receive_timeout(100)
    with NonBlockingReader(cfg.build(), results_queue_size=100) as reader:
        yield reader


@pytest.fixture
def client_zmq_sink_config(client_zmq_sink_endpoint: str) -> ZMQWriterConfig:
    return ZMQWriterConfig(
        max_inflight_messages=1000,
        endpoint=client_zmq_sink_endpoint,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def server_zmq_sink_config(server_zmq_sink_endpoint: str) -> ZMQWriterConfig:
    return ZMQWriterConfig(
        max_inflight_messages=1000,
        endpoint=server_zmq_sink_endpoint,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def var_zmq_sink_config(var_zmq_sink_endpoint: str) -> ZMQWriterConfig:
    return ZMQWriterConfig(
        max_inflight_messages=1000,
        endpoint=var_zmq_sink_endpoint,
        send_timeout=100,
        receive_timeout=100,
    )


@pytest.fixture
def client_zmq_src_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"bind:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def server_zmq_src_endpoint(port_pool: PortPool) -> Generator[str]:
    with port_pool.lease() as port:
        yield f"connect:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def var_zmq_src_endpoint(
    port_pool: PortPool, connect_dir2: ConnectDir, socket_type: SocketType
) -> Generator[str]:
    with port_pool.lease() as port:
        if socket_type == "tcp":
            yield f"{connect_dir2}:tcp://127.0.0.1:{port}"
        else:
            yield f"{connect_dir2}:ipc:///tmp/cloudpin/{port}"


@pytest.fixture
def client_zmq_writer(client_zmq_src_endpoint: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(client_zmq_src_endpoint)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def server_zmq_writer(server_zmq_src_endpoint: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(server_zmq_src_endpoint)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def var_zmq_writer(var_zmq_src_endpoint: str) -> Generator[NonBlockingWriter]:
    cfg = WriterConfigBuilder(f"dealer+{opposite_dir_url(var_zmq_src_endpoint)}")
    cfg.with_send_timeout(100)
    cfg.with_receive_timeout(100)
    with NonBlockingWriter(cfg.build(), max_inflight_messages=100) as writer:
        yield writer


@pytest.fixture
def client_zmq_src_config(client_zmq_src_endpoint: str) -> ZMQReaderConfig:
    return ZMQReaderConfig(
        results_queue_size=1000, endpoint=client_zmq_src_endpoint, receive_timeout=1000
    )


@pytest.fixture
def server_zmq_src_config(server_zmq_src_endpoint: str) -> ZMQReaderConfig:
    return ZMQReaderConfig(
        results_queue_size=1000, endpoint=server_zmq_src_endpoint, receive_timeout=1000
    )


@pytest.fixture
def var_zmq_src_config(var_zmq_src_endpoint: str) -> ZMQReaderConfig:
    return ZMQReaderConfig(
        results_queue_size=1000, endpoint=var_zmq_src_endpoint, receive_timeout=1000
    )
