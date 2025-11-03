from struct import Struct
from typing import NamedTuple

from savant_rs.utils import serialization
from savant_rs.utils.serialization import Message

FRAME_HEAD_SIZE = 8
FRAME_HEAD_FORMAT = Struct("<ll")
API_KEY_HEADER = "x-api-key"


class FrameData(NamedTuple):
    topic: bytes
    message: Message
    extra: bytes


def pack_stream_frame(topic: bytes, message: Message, extra: bytes | None) -> bytes:
    body = serialization.save_message_to_bytes(message)
    extra = extra or b""
    head = FRAME_HEAD_FORMAT.pack(len(topic), len(body))
    return b"".join([head, topic, body, extra])


def unpack_stream_frame(payload: bytes) -> FrameData:
    topic_size, body_size = FRAME_HEAD_FORMAT.unpack_from(payload)
    topic_idx = FRAME_HEAD_SIZE
    body_idx = topic_idx + topic_size
    extra_idx = body_idx + body_size

    topic = payload[topic_idx:body_idx]
    body = payload[body_idx:extra_idx]
    extra = payload[extra_idx:]

    msg = serialization.load_message_from_bytes(body)
    return FrameData(topic, msg, extra)
