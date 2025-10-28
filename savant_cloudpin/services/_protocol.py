from struct import Struct
from typing import NamedTuple
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse

from picows import WSFrame
from savant_rs.utils import serialization
from savant_rs.utils.serialization import Message

UPSTREAM_PATH = "upstream"
DOWNSTREAM_PATH = "downsteam"
FRAME_HEAD_SIZE = 8
FRAME_HEAD_FORMAT = Struct("<ll")
API_KEY_HEADER = "x-api-key"


def _normalize_base_url(base_url: str) -> str:
    scheme, netloc, path, params, query, fragment = urlparse(base_url)

    if not path or path.endswith("/"):
        return base_url

    components = ParseResult(
        scheme=scheme,
        netloc=netloc,
        path=path + "/",
        params=params,
        query=query,
        fragment=fragment,
    )
    return str(urlunparse(components))


def upstream_url(base_url: str) -> str:
    base_url = _normalize_base_url(base_url)
    return urljoin(base_url, UPSTREAM_PATH)


def downstream_url(base_url: str) -> str:
    base_url = _normalize_base_url(base_url)
    return urljoin(base_url, DOWNSTREAM_PATH)


class FrameData(NamedTuple):
    topic: bytes
    message: Message
    extra: bytes


def pack_stream_frame(topic: bytes, message: Message, extra: bytes | None) -> bytes:
    body = serialization.save_message_to_bytes(message)
    extra = extra or b""
    head = FRAME_HEAD_FORMAT.pack(len(topic), len(body))
    return b"".join([head, topic, body, extra])


def unpack_stream_frame(frame: WSFrame) -> FrameData:
    payload = frame.get_payload_as_bytes()
    topic_size, body_size = FRAME_HEAD_FORMAT.unpack_from(payload)
    topic_idx = FRAME_HEAD_SIZE
    body_idx = topic_idx + topic_size
    extra_idx = body_idx + body_size

    topic = payload[topic_idx:body_idx]
    body = payload[body_idx:extra_idx]
    extra = payload[extra_idx:]

    msg = serialization.load_message_from_bytes(body)
    return FrameData(topic, msg, extra)
