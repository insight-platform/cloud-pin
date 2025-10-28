import asyncio
import unittest
import unittest.mock
from typing import NamedTuple, Self
from unittest.mock import Mock

import pytest
from faker import Faker
from savant_rs.primitives import Attribute, AttributeValue, UserData
from savant_rs.utils import serialization
from savant_rs.utils.serialization import Message
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.cfg import ServerServiceConfig
from savant_cloudpin.services import ClientService, ServerService
from savant_cloudpin.services._pumps._outbound import OutboundWSListener
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter, ReaderResult
from tests import helpers

fake = Faker()


class MessageData(NamedTuple):
    topic: bytes
    msg: serialization.Message
    extra: bytes | None

    def is_same(self, res: ReaderResult | None) -> bool:
        if not isinstance(res, ReaderResultMessage):
            return False
        if self.topic != res.topic or self.extra != res.data(0):
            return False

        msg = serialization.save_message_to_bytes(self.msg)
        res_msg = serialization.save_message_to_bytes(res.message)
        return msg == res_msg

    @classmethod
    def fake(cls, large: bool = False) -> Self:
        topic = fake.domain_word()
        extra = fake.sentence(nb_words=100000 if large else 10)

        match fake.random_element(["unknown", "user_data"]):
            case "user_data":
                values = [AttributeValue.string(fake.pystr())]
                attr = Attribute(fake.domain_name(), fake.pystr(), values, None)
                user_data = UserData(fake.uuid4())
                user_data.set_attribute(attr)
                msg = user_data.to_message()
            case _:
                msg = Message.unknown(fake.sentence())

        return cls(topic=topic.encode(), msg=msg, extra=extra.encode())


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_with_client_variants(
    var_client: ClientService,
    server: ServerService,
    var_writer: NonBlockingWriter,
    var_reader: NonBlockingReader,
) -> None:
    data = MessageData.fake()

    var_writer.start()
    var_reader.start()

    asyncio.create_task(server.run())
    await server.started.wait()

    asyncio.create_task(var_client.run())
    await var_client.started.wait()

    var_writer.send_message(*data)
    result = await helpers.zmq.receive_result(var_reader)

    assert isinstance(result, ReaderResultMessage)
    assert data.is_same(result)


@pytest.mark.asyncio
@pytest.mark.usefixtures("var_identity_pipeline")
async def test_identity_pipeline_with_server_variants(
    client: ClientService,
    var_server: ServerService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    data = MessageData.fake()

    client_writer.start()
    client_reader.start()

    asyncio.create_task(var_server.run())
    await var_server.started.wait()

    asyncio.create_task(client.run())
    await client.started.wait()

    client_writer.send_message(*data)
    result = await helpers.zmq.receive_result(client_reader)

    assert isinstance(result, ReaderResultMessage)
    assert data.is_same(result)


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_when_invalid_client_cert(
    another_cert_client: ClientService, server: ServerService
) -> None:
    asyncio.create_task(server.run())
    await server.started.wait()

    with pytest.raises(ConnectionError) as error_info:
        await asyncio.wait_for(another_cert_client.run(), 5)

    assert str(error_info.value.args[0]).startswith("Error connecting")
    assert not another_cert_client.running


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_when_invalid_server_cert(
    client: ClientService, another_cert_server: ServerService
) -> None:
    asyncio.create_task(another_cert_server.run())
    await another_cert_server.started.wait()

    with pytest.raises(ConnectionError) as error_info:
        await asyncio.wait_for(client.run(), 5)

    assert str(error_info.value.args[0]).startswith("Error connecting")
    assert not client.running


@pytest.mark.asyncio
@pytest.mark.usefixtures("started_client_side", "identity_pipeline")
async def test_identity_pipeline_when_same_cert_server(
    same_cert_server: ServerService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    data = MessageData.fake()

    asyncio.create_task(same_cert_server.run())
    await same_cert_server.started.wait()

    client_writer.send_message(*data)
    result = await helpers.zmq.receive_result(client_reader)

    assert isinstance(result, ReaderResultMessage)
    assert data.is_same(result)


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_when_invalid_apikey(
    another_apikey_client: ClientService, server: ServerService
) -> None:
    asyncio.create_task(server.run())
    await server.started.wait()

    with pytest.raises(ConnectionError) as error_info:
        await asyncio.wait_for(another_apikey_client.run(), 5)

    assert str(error_info.value.args[0]).startswith("Error connecting")
    assert not another_apikey_client.running


@pytest.mark.asyncio
@pytest.mark.usefixtures("started_client_side", "identity_pipeline")
async def test_identity_pipeline_when_reconnect(
    server_config: ServerServiceConfig,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    first_data = MessageData.fake()
    reconnect_data = MessageData.fake()

    async with ServerService(server_config) as server:
        asyncio.create_task(server.run())
        await server.started.wait()

        client_writer.send_message(*first_data)
        first_res = await helpers.zmq.receive_result(client_reader)

    client_writer.send_message(*reconnect_data)
    client_writer.send_message(*reconnect_data)

    async with ServerService(server_config) as server:
        asyncio.create_task(server.run())
        await server.started.wait()

        client_writer.send_message(*reconnect_data)
        client_writer.send_message(*reconnect_data)
        reconnect_res = await helpers.zmq.receive_result(client_reader)

    assert isinstance(first_res, ReaderResultMessage)
    assert first_data.is_same(first_res)
    assert isinstance(reconnect_res, ReaderResultMessage)
    assert reconnect_data.is_same(reconnect_res)


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_when_nossl(
    nossl_client: ClientService,
    nossl_server: ServerService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    data = MessageData.fake()

    client_writer.start()
    client_reader.start()

    asyncio.create_task(nossl_server.run())
    await nossl_server.started.wait()

    asyncio.create_task(nossl_client.run())
    await nossl_client.started.wait()

    client_writer.send_message(*data)
    result = await helpers.zmq.receive_result(client_reader)

    assert isinstance(result, ReaderResultMessage)
    assert data.is_same(result)


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
async def test_identity_pipeline_when_sequence(
    client: ClientService,
    server: ServerService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    count = fake.random_int(8, 32)
    sequence = [MessageData.fake() for _ in range(count)]

    client_writer.start()
    client_reader.start()

    asyncio.create_task(server.run())
    await server.started.wait()

    asyncio.create_task(client.run())
    await client.started.wait()

    results_sink = asyncio.create_task(
        helpers.zmq.receive_results(client_reader, count, timeout=10)
    )
    for data in sequence:
        client_writer.send_message(*data)
    results = await results_sink

    assert len(results) == count
    assert all(isinstance(res, ReaderResultMessage) for res in results)
    assert all(expected.is_same(res) for res, expected in zip(results, sequence))


original_pause_writing = OutboundWSListener.pause_writing


@pytest.mark.asyncio
@pytest.mark.usefixtures("identity_pipeline")
@unittest.mock.patch.object(OutboundWSListener, "pause_writing", autospec=True)
async def test_identity_pipeline_that_pause_under_pressure(
    pause_writing_mock: Mock,
    client: ClientService,
    server: ServerService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    pause_writing_mock.side_effect = original_pause_writing
    count = 1000
    sequence = [MessageData.fake(large=True) for _ in range(count)]

    client_writer.start()
    client_reader.start()

    asyncio.create_task(server.run())
    await server.started.wait()

    asyncio.create_task(client.run())
    await client.started.wait()

    results_sink = asyncio.create_task(
        helpers.zmq.receive_results(client_reader, count, timeout=30)
    )
    for data in sequence:
        client_writer.send_message(*data)
        await asyncio.sleep(0)
    results = await results_sink

    assert pause_writing_mock.called
    assert len(results) == count
    assert all(expected.is_same(res) for res, expected in zip(results, sequence))


@pytest.mark.asyncio
async def test_messages_at_every_ends(
    server: ServerService,
    server_writer: NonBlockingWriter,
    server_reader: NonBlockingReader,
    client: ClientService,
    client_writer: NonBlockingWriter,
    client_reader: NonBlockingReader,
) -> None:
    original_data = MessageData.fake()
    processed_data = MessageData.fake()

    server_writer.start()
    server_reader.start()
    client_writer.start()
    client_reader.start()

    asyncio.create_task(server.run())
    await server.started.wait()

    asyncio.create_task(client.run())
    await client.started.wait()

    client_writer.send_message(*original_data)
    server_input = await helpers.zmq.receive_result(server_reader)
    server_writer.send_message(*processed_data)
    client_output = await helpers.zmq.receive_result(client_reader, timeout=3)

    assert isinstance(server_input, ReaderResultMessage)
    assert original_data.is_same(server_input)
    assert isinstance(client_output, ReaderResultMessage)
    assert processed_data.is_same(client_output)
