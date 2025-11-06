import json
from typing import NamedTuple, Self

from faker import Faker
from savant_rs.primitives import (
    Attribute,
    AttributeValue,
    UserData,
    VideoFrame,
    VideoFrameContent,
)
from savant_rs.utils import serialization
from savant_rs.utils.serialization import Message
from savant_rs.zmq import ReaderResultMessage

from savant_cloudpin.zmq import ReaderResult

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
        if self.is_same_video_frame(res.message.as_video_frame()):
            return True

        msg_bytes = serialization.save_message_to_bytes(self.msg)
        res_bytes = serialization.save_message_to_bytes(res.message)
        return msg_bytes == res_bytes

    def is_same_video_frame(self, res: VideoFrame | None) -> bool:
        video_frame = self.msg.as_video_frame()
        if not video_frame or not res:
            return False
        js = json.loads(video_frame.json)
        res_js = json.loads(res.json)
        del js["attributes"]
        del js["version"]
        del res_js["attributes"]
        del res_js["version"]
        return js == res_js and video_frame.content.get_data() == res.content.get_data()

    @classmethod
    def fake_video_frame(cls) -> VideoFrame:
        width, height = fake.random_element([(176, 144), (224, 144), (240, 160)])
        framerate = fake.random_element(["30/1, 24/1"])
        content = VideoFrameContent.internal(
            fake.image(size=(width, height), image_format="jpeg")
        )
        values = [AttributeValue.string(fake.pystr())]
        attr = Attribute(fake.domain_name(), fake.pystr(), values, None)
        video_frame = VideoFrame(
            source_id=fake.uuid4(),
            framerate=framerate,
            width=width,
            height=height,
            content=content,
        )
        video_frame.set_attribute(attr)
        return video_frame

    @classmethod
    def fake(cls, large: bool = False) -> Self:
        topic = fake.domain_word()
        extra = fake.sentence(nb_words=100000 if large else 10)

        match fake.random_element(["unknown", "user_data", "video_frame"]):
            case "video_frame":
                msg = cls.fake_video_frame().to_message()
            case "user_data":
                user_data = UserData(fake.uuid4())
                values = [AttributeValue.string(fake.pystr())]
                attr = Attribute(fake.domain_name(), fake.pystr(), values, None)
                user_data.set_attribute(attr)
                msg = user_data.to_message()
            case _:
                msg = Message.unknown(fake.sentence())

        return cls(topic=topic.encode(), msg=msg, extra=extra.encode())
