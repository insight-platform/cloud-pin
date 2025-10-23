import asyncio

import pytest
from faker import Faker
from savant_rs.utils import serialization
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.services import ClientService, ServerService
from savant_cloudpin.zmq import NonBlockingReader, NonBlockingWriter

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

    sink.start()
    source.start()

    asyncio.create_task(server_service.run())
    await server_service.started.wait()

    asyncio.create_task(client_service.run())
    await client_service.started.wait()

    msg = serialization.Message.unknown(fake.sentence())
    source.send_message(topic, msg, extra_data)

    while (
        not isinstance(result := sink.try_receive(), ReaderResultMessage)
        and server_service.running
        and client_service.running
    ):
        await asyncio.sleep(0.01)

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
