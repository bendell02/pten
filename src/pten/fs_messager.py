"""
pten.fs_messager
~~~~~~~~~~~~~~~~

This module implements the Messager class for Feishu.
"""

import json
import time
from pathlib import Path
from queue import Queue
from typing import Optional

from . import logger
from .fs_api import BOT_API_TYPE, CORP_API_TYPE, FsBotApi, FsCorpApi
from .keys import Keys


class FsMsgSender:
    """
    The parent class of all the notify classes
    """

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
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
            "receive_id_error": "消息接收者(receive_id)不能为空",
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

    @staticmethod
    def _build_simple_card(title, content, template="blue"):
        """构造一个带标题和正文的简单卡片，供各 sender 的 send_card 共用"""
        return {
            "header": {
                "template": template,
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}}
            ],
        }


class FsBotMsgSender(FsMsgSender):
    """
    飞书机器人，支持文本、卡片类型数据的发送
    """

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
        super().__init__(keys_filepath, keys=keys, **kwargs)
        self.api = FsBotApi(keys_filepath, keys=keys)
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
            return {"code": -1, "msg": self.errmsgs["text_error"]}
        data = {
            "content": {
                "text": content,
            }
        }
        return self._send(msg_type="text", data=data)

    def send_card(self, title, content, template="blue"):
        """
        发送卡片消息(interactive)，构造一个带标题和正文的简单卡片
        :param title: 卡片标题
        :param content: 卡片正文，支持 lark_md 语法
        :param template: 卡片头部配色模板，默认 blue，可选 red/orange/yellow/green/indigo/grey 等
        :return: 消息发送结果
        卡片结构参考 https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/feishu-cards/card-json-structure/credat-card
        """
        if not (title and content):
            logger.error(self.errmsgs["card_error"])
            return {"code": -1, "msg": self.errmsgs["card_error"]}
        card = self._build_simple_card(title, content, template)
        return self._send(msg_type="interactive", data={"card": card})


class FsAppMsgSender(FsMsgSender):
    """
    飞书自建应用消息推送器：把消息发给指定用户或群聊，
    鉴权由 FsCorpApi 的 tenant_access_token 完成
    """

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
        super().__init__(keys_filepath, keys=keys, **kwargs)
        self.api = FsCorpApi(keys_filepath, keys=keys)
        # [fs] 可选配置默认接收者：未显式传 receive_id 的发送会发给它
        self.default_receive_id = self.keys.get_fs_receive_id()
        self.default_receive_id_type = self.keys.get_fs_receive_id_type()

    def _send(self, msg_type="", content=None, receive_id=None, receive_id_type=None):
        """
        统一内部发送接口，供不同消息推送方法调用
        :param msg_type: 消息类型，如 text / interactive
        :param content: 消息体对象，im 接口要求 content 为 JSON 字符串，发送前序列化
        :param receive_id: 消息接收者，缺省回退 [fs] 配置的默认接收者
        :param receive_id_type: 接收者 ID 类型：open_id / user_id / union_id / email / chat_id，
            使用默认接收者时回退 [fs] 配置的类型，否则 open_id
        :return: 消息发送结果
        """
        if not receive_id:
            receive_id = self.default_receive_id
            # 默认接收者配套的 ID 类型（未配置则回退 open_id）
            if not receive_id_type:
                receive_id_type = self.default_receive_id_type

        if not receive_id:
            logger.error(self.errmsgs["receive_id_error"])
            return {"code": -1, "msg": self.errmsgs["receive_id_error"]}

        if not receive_id_type:
            receive_id_type = "open_id"

        data = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        }
        # receive_id_type 是查询参数，发送前替换端点 URL 中的占位符
        shortUrl, method = CORP_API_TYPE["MESSAGE_SEND"]
        return self.api.http_call(
            [shortUrl.replace("RECEIVE_ID_TYPE", receive_id_type), method], data
        )

    def send_text(self, content, receive_id=None, receive_id_type=None):
        """
        发送文本消息给用户或群聊
        :param content: 文本内容，最长不超过150个字符
        :param receive_id: 消息接收者，缺省用 [fs] 配置的默认接收者
        :param receive_id_type: 接收者 ID 类型，缺省 open_id（使用默认接收者时可用 [fs] 配置覆盖）
        :return: 消息发送结果
        """
        if not content:
            logger.error(self.errmsgs["text_error"])
            return {"code": -1, "msg": self.errmsgs["text_error"]}
        return self._send(
            msg_type="text",
            content={"text": content},
            receive_id=receive_id,
            receive_id_type=receive_id_type,
        )

    def send_card(
        self,
        title,
        content,
        template="blue",
        receive_id=None,
        receive_id_type=None,
    ):
        """
        发送卡片消息(interactive)给用户或群聊，构造一个带标题和正文的简单卡片
        :param title: 卡片标题
        :param content: 卡片正文，支持 lark_md 语法
        :param template: 卡片头部配色模板，默认 blue，可选 red/orange/yellow/green/indigo/grey 等
        :param receive_id: 消息接收者，缺省用 [fs] 配置的默认接收者
        :param receive_id_type: 接收者 ID 类型，缺省 open_id（使用默认接收者时可用 [fs] 配置覆盖）
        :return: 消息发送结果
        卡片结构参考 https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/feishu-cards/card-json-structure/credat-card
        """
        if not (title and content):
            logger.error(self.errmsgs["card_error"])
            return {"code": -1, "msg": self.errmsgs["card_error"]}
        card = self._build_simple_card(title, content, template)
        return self._send(
            msg_type="interactive",
            content=card,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
        )
