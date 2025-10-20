import asyncio

import pytest
from faker import Faker
from savant_rs.utils import serialization
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.services import ClientService
from savant_cloudpin.zmq import Reader, Writer

fake = Faker()


@pytest.mark.asyncio
async def test_identity_pipeline(
    client_service: ClientService, source: Writer, sink: Reader
) -> None:
    topic = fake.domain_word().encode()
    extra_data = fake.sentence().encode()

    sink.start()
    source.start()
    asyncio.create_task(client_service.run())

    while not client_service.running:
        await asyncio.sleep(0.01)

    msg = serialization.Message.unknown(fake.sentence())
    source.send(topic, msg, extra_data)

    while (
        not isinstance(result := sink.try_receive(), ReaderResultMessage)
        and client_service.running
    ):
        await asyncio.sleep(0.01)

    assert isinstance(result, ReaderResultMessage)
    assert result.topic == topic
    assert result.message.is_unknown()
    assert result.data(0) == extra_data
