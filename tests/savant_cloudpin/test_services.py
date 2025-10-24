import asyncio

import pytest
import pytest_asyncio
from faker import Faker
from savant_rs.utils import serialization
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.services import ClientService, ServerService
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter
from tests import helpers

fake = Faker()


@pytest.mark.asyncio
async def test_identity_pipeline(
    client_service: ClientService,
    server_service: ServerService,
    source: NonBlockingWriter,
    sink: NonBlockingReader,
) -> None:
    topic = fake.domain_word().encode()
    extra_data = fake.sentence().encode()
    msg = serialization.Message.unknown(fake.sentence())

    sink.start()
    source.start()

    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    asyncio.create_task(client_service.run())
    await client_service.started.wait()

    source.send_message(topic, msg, extra_data)
    result = await helpers.zmq.receive_result(sink)

    assert isinstance(result, ReaderResultMessage)
    assert result.topic == topic
    assert result.message.is_unknown()
    assert result.data(0) == extra_data


@pytest.mark.asyncio
async def test_identity_pipeline_when_invalid_client_cert(
    another_cert_client_service: ClientService, server_service: ServerService
) -> None:
    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    with pytest.raises(ConnectionError) as error_info:
        await another_cert_client_service.run()

    assert str(error_info.value.args[0]).startswith("Error connecting")
    assert not another_cert_client_service.running


@pytest.mark.asyncio
async def test_identity_pipeline_when_invalid_apikey(
    another_apikey_client_service: ClientService, server_service: ServerService
) -> None:
    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    with pytest.raises(ConnectionError) as error_info:
        await another_apikey_client_service.run()

    assert str(error_info.value.args[0]).startswith("Error connecting")
    assert not another_apikey_client_service.running


@pytest_asyncio.fixture
async def started_client_side(
    source: NonBlockingWriter, sink: NonBlockingReader, client_service: ClientService
) -> None:
    sink.start()
    source.start()

    asyncio.create_task(client_service.run())
    await client_service.started.wait()


@pytest.mark.asyncio
async def test_identity_pipeline_when_reconnect(
    started_client_side: None,
    server_service: ServerService,
    source: NonBlockingWriter,
    sink: NonBlockingReader,
) -> None:
    topic1 = fake.domain_word().encode()
    topic2 = fake.domain_word().encode()
    extra1 = fake.sentence().encode()
    extra2 = fake.sentence().encode()
    msg1 = serialization.Message.unknown(fake.sentence())
    msg2 = serialization.Message.unknown(fake.sentence())

    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    source.send_message(topic1, msg1, extra1)
    res1 = await helpers.zmq.receive_result(sink)

    await server_service.stop()

    source.send_message(topic2, msg2, extra2)

    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    res2 = await helpers.zmq.receive_result(sink)

    assert isinstance(res1, ReaderResultMessage)
    assert isinstance(res2, ReaderResultMessage)
    assert res1.topic == topic1
    assert res2.topic == topic2
    assert res1.message.is_unknown() and res2.message.is_unknown()
    assert res1.data(0) == extra1
    assert res2.data(0) == extra2
