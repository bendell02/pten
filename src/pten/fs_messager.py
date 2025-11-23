"""
pten.wwmessager
~~~~~~~~~~~~

This module implements the Messager class.

Many codes are from “corpwechatbot"

"""

from . import logger
from .keys import Keys
from .fs_api import BotApi, BOT_API_TYPE
import base64
from hashlib import md5
from pathlib import Path
from queue import Queue
import time
from typing import Optional


class MsgSender:
    """
    The parent class of all the notify classes
    """

    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None, **kwargs):
        self.keys = keys if keys else Keys(keys_filepath)
        self.errmsgs = {
            "image_error": "图片文件不合法",
            "text_error": "文本消息不合法",
            "news_error": "图文消息内容不合法",
            "markdown_error": "markdown内容不合法",
            "voice_error": "语音文件不合法",
            "video_error": "视频文件不合法",
            "file_error": "文件不合法",
            "card_error": "卡片消息不合法",
            "media_error": "media_id获取失败",
            "mpnews_error": "mp图文消息不合法",
            "taskcard_error": "任务卡片消息不合法",
            "create_chat_error": "群聊创建失败，人数不能低于2",
        }

    def _get_media_id(self, media_type: str, p_media: Path):
        """
        获取media id，微信要求文件先上传到其后端服务器，再获取相应media id
        :param media_type:
        :param p_media:
        :return:
        """
        raise NotImplementedError

    def _send(
        self,
        msg_type: str = "",
        data: dict = {},
        media_path: Optional[str] = "",
        **kwargs,
    ):
        """
        :param msg_type:
        :param data:
        :param media_path:
        :param kwargs:
        :return:
        """

    def send_text(self, *args, **kwargs):
        """
        send text message
        :return:
        """
        raise NotImplementedError

    def send_markdown(self, *args, **kwargs):
        """
        send markdown message
        :return:
        """
        raise NotImplementedError

    def send_image(self, *args, **kwargs):
        """
        send image message
        :return:
        """
        raise NotImplementedError

    def send_voice(self, *args, **kwargs):
        """
        发送语音消息
        """
        raise NotImplementedError

    def send_video(self, *args, **kwargs):
        """
        发送视频消息
        """
        raise NotImplementedError

    def send_news(self, *args, **kwargs):
        """
        send news
        :return:
        """
        raise NotImplementedError

    def send_file(self, *args, **kwargs):
        """
        send file
        :return:
        """
        raise NotImplementedError

    def send_mpnews(self, *args, **kwargs):
        """
        发送mpnews图文消息
        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError

    def send_card(self, *args, **kwargs):
        """
        发送卡片消息
        """
        raise NotImplementedError

    def send_miniprogram_notice(self, *args, **kwargs):
        raise NotImplementedError

    def send_template_card(self, *args, **kwargs):
        """
        发送模板卡片消息
        """
        raise NotImplementedError


class BotMsgSender(MsgSender):
    """
    企业微信机器人，支持文本、markdown、图片、图文、文件、语音类型数据的发送
    """

    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None, **kwargs):
        super().__init__(keys_filepath, keys=keys, **kwargs)
        self.api = BotApi(keys_filepath, keys=keys)
        self.queue = Queue(20)  # 机器人消息频率限制为每分钟不超过20条消息

    def _send(
        self,
        msg_type: str = "",
        data: dict = {},
        **kwargs,
    ):
        """
        :param msg_type:
        :param data:
        :param media_path:
        :return:
        """
        data["msg_type"] = msg_type

        now = time.time()
        self.queue.put(now)
        if self.queue.full():
            # 限制每分钟20条消息，超限则进行睡眠等待
            interval_time = now - self.queue.get()
            if interval_time < 60:
                sleep_time = int(60 - interval_time) + 1
                logger.debug(f"机器人每分钟限制20条消息，需等待 {sleep_time} s")
                time.sleep(sleep_time)

        return self.api.http_call(BOT_API_TYPE["WEBHOOK_SEND"], data)

    def send_text(self, content):
        """
        发送文本消息，
        :param content: 文本内容，最长不能超过2048字节，utf-8编码
        :return: 消息发送结果
        """
        if not content:
            logger.error(self.errmsgs["text_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["text_error"]}
        data = {
            "content": {
                "text": content,
            }
        }
        return self._send(msg_type="text", data=data)
