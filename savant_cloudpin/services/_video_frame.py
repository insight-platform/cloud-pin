import itertools
from datetime import datetime, timezone
from functools import cached_property
from typing import Final, Literal

from savant_rs.primitives import Attribute, AttributeValue
from savant_rs.utils.serialization import Message

ATTR_NS: Final = "CloudPin"
ATTR: Final = "timings"

type ValueLabel = Literal[
    "client_source_timestamp",
    "server_sink_timestamp",
    "server_source_timestamp",
    "client_sink_timestamp",
]
LABEL_CLIENT_SOURCE: Final[ValueLabel] = "client_source_timestamp"
LABEL_SERVER_SINK: Final[ValueLabel] = "server_sink_timestamp"
LABEL_SERVER_SOURCE: Final[ValueLabel] = "server_source_timestamp"
LABEL_CLIENT_SINK: Final[ValueLabel] = "client_sink_timestamp"


class VideoFrameTimings:
    def __init__(self, message: Message) -> None:
        self.message = message

    def reset_cache(self) -> None:
        if "values" in self.__dict__:
            del self.__dict__["values"]

    @cached_property
    def values(self) -> dict[str, float] | None:
        video_frame = self.message.as_video_frame()
        timings = video_frame.get_attribute(ATTR_NS, ATTR) if video_frame else None
        if not timings or not timings.values:
            return None

        labels = (
            val.as_string() for val in itertools.islice(timings.values, 0, None, 2)
        )
        timestamps = (
            val.as_float() for val in itertools.islice(timings.values, 1, None, 2)
        )
        return {
            label: timestamp
            for label, timestamp in zip(labels, timestamps)
            if label and timestamp is not None
        }

    def append_timing(self, label: ValueLabel, truncate: bool = False) -> None:
        video_frame = self.message.as_video_frame()
        if not video_frame:
            return

        timings = video_frame.get_attribute(ATTR_NS, ATTR)
        if not timings or truncate:
            timings = Attribute(ATTR_NS, ATTR, [], None)

        values = timings.values
        timestamp = datetime.now(timezone.utc).timestamp()
        values.append(AttributeValue.string(label))
        values.append(AttributeValue.float(timestamp))

        timings.values = values
        video_frame.set_attribute(timings)
        self.reset_cache()

    def get_delay(self, start_label: ValueLabel, end_label: ValueLabel) -> float | None:
        if not self.values:
            return None
        start = self.values.get(start_label, None)
        end = self.values.get(end_label, None)
        if start is None or end is None:
            return None
        return end - start
