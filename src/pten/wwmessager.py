"""
pten.wwmessager
~~~~~~~~~~~~

This module implements the Messager class.

Many codes are from “corpwechatbot"

"""

import base64
import time
from hashlib import md5
from pathlib import Path
from queue import Queue
from typing import Optional

from . import logger
from .keys import Keys
from .wwapi import BOT_API_TYPE, CORP_API_TYPE, BotApi, CorpApi


def reply_text(decrypt_data, content):
    sRespData = """
<xml>
   <ToUserName>{to_username}</ToUserName>
   <FromUserName>{from_username}</FromUserName> 
   <CreateTime>{create_time}</CreateTime>
   <MsgType>text</MsgType>
   <Content>{content}</Content>
</xml>
""".format(
        to_username=decrypt_data["ToUserName"],
        from_username=decrypt_data["FromUserName"],
        create_time=decrypt_data["CreateTime"],
        content=content,
    )

    return sRespData


def is_image(image_path: str):
    p_image = Path(image_path)
    if not p_image.is_file():
        return False
    if p_image.suffix != ".jpg" and p_image.suffix != ".png":
        return False
    if p_image.stat().st_size > 2 * 1024 * 1024 or p_image.stat().st_size <= 5:
        # image no more than 2M
        return False
    return True


def is_voice(voice_path: str):
    p_voice = Path(voice_path)
    if not p_voice.is_file():
        return False
    if p_voice.suffix != ".amr":
        return False
    if p_voice.stat().st_size > 2 * 1024 * 1024 or p_voice.stat().st_size <= 5:
        # voice no more than 2M
        return False
    return True


def is_video(video_path: str):
    p_video = Path(video_path)
    if not p_video.is_file():
        return False
    if p_video.suffix != ".mp4":
        return False
    if p_video.stat().st_size > 10 * 1024 * 1024 or p_video.stat().st_size <= 5:
        # video no more than 10M
        return False
    return True


def is_file(file_path: str):
    p_file = Path(file_path)
    if not p_file.is_file():
        return False
    if p_file.stat().st_size > 20 * 1024 * 1024 or p_file.stat().st_size <= 5:
        # file no more than 2M
        return False
    return True


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

    def _get_media_id(self, media_type: str, p_media: Path):
        if media_type not in ["voice", "file"]:
            raise ValueError("bot media_type can only be voice or file")

        data = {"file": p_media.open("rb")}
        response = self.api.http_call(
            BOT_API_TYPE["WEBHOOK_MEDIA_UPLOAD"],
            {"type": media_type, "files": data},
        )

        return response

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
        :return:
        """
        data["msgtype"] = msg_type

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

    def send_text(self, content, mentioned_list=[], mentioned_mobile_list=[]):
        """
        发送文本消息，
        :param content: 文本内容，最长不能超过2048字节，utf-8编码
        :param mentioned_list: userid列表，提醒群众某个成员，userid通过企业通讯录查看，'@all'则提醒所有人
        :param mentioned_mobile_list: 手机号列表，提醒手机号对应的成员，'@all'代表所有人，当不清楚userid时可替换
        :return: 消息发送结果
        """
        if not content:
            logger.error(self.errmsgs["text_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["text_error"]}
        data = {
            "text": {
                "content": content,
                "mentioned_list": mentioned_list,
                "mentioned_mobile_list": mentioned_mobile_list,
            }
        }
        return self._send(msg_type="text", data=data)

    def send_markdown(self, content=""):
        """
        发送markdown类型数据，支持markdown语法
        :param content: mardkown原始数据或markdown文件路径
        :return: 消息发送结果
        """
        if not content:
            logger.error(self.errmsgs["markdown_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["markdown_error"]}
        if content.endswith(".md"):
            try:
                content = Path(content).read_text()
            except (OSError, FileNotFoundError):
                logger.warning(
                    "你可能正在尝试发送一个markdown文件，但文件并不存在或文件名过长，将直接发送内容."
                )
        data = {"markdown": {"content": content}}
        return self._send(msg_type="markdown", data=data)

    def send_image(self, image_path=""):
        """
        发送图片类型，限制大小2M，支持JPG，PNG格式
        :param image_path: 图片文件路径
        :return: result
        """
        if not is_image(image_path):
            logger.error(self.errmsgs["image_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["image_error"]}

        img_content = Path(image_path).open("rb").read()
        img_base64 = base64.b64encode(img_content).decode()
        img_md5 = md5(img_content).hexdigest()
        data = {
            "image": {
                "base64": img_base64,
                "md5": img_md5,
            }
        }
        return self._send(msg_type="image", data=data)

    def send_voice(self, voice_path: str):
        """
        发送语音
        :param voice_path:
        :return:
        """
        if not is_voice(voice_path):
            logger.error(self.errmsgs["voice_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["voice_error"]}

        media_res = self._get_media_id(media_type="voice", p_media=Path(voice_path))
        data = {
            "voice": {
                "media_id": media_res.get("media_id", ""),
            }
        }

        return self._send(msg_type="voice", data=data)

    def send_news(self, title="", desp="", url="", picurl=""):
        """
        发送图文消息
        :param title: 图文标题，不超过128个字节，超过会自动截断
        :param desp: 图文描述，可选，不超过512个字节，超过会自动截断
        :param url: 跳转链接
        :param picurl: 图片url，支持JPG、PNG格式，较好的效果为大图 1068*455，小图150*150。
        :return:
        """
        if not (title and url):
            logger.error(self.errmsgs["news_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["news_error"]}
        data = {
            "news": {
                "articles": [
                    {"title": title, "description": desp, "url": url, "picurl": picurl}
                ]
            }
        }
        return self._send(msg_type="news", data=data)

    def send_file(self, file_path: str):
        """
        发送文件
        :param file_path:
        :return:
        """
        if not is_file(file_path):
            logger.error(self.errmsgs["file_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["file_error"]}

        media_res = self._get_media_id(media_type="file", p_media=Path(file_path))
        data = {
            "file": {
                "media_id": media_res.get("media_id", ""),
            }
        }

        return self._send(msg_type="file", data=data)

    def send_template_card(self, template_card, *args, **kwargs):
        data = {"template_card": template_card}

        return self._send(msg_type="template_card", data=data)


class AppMsgSender(MsgSender):
    """
    应用消息推送器，支持文本、图片、语音、视频、文件、文本卡片、图文、markdown消息推送
    """

    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None, **kwargs):
        """
        :param corpid: 企业id
        :param corpsecret: 应用密钥
        :param agentid: 应用id
        """
        super().__init__(keys_filepath, keys=keys, **kwargs)
        self.api = CorpApi(keys_filepath, keys=keys)
        self.agentid = self.keys.get_app_agentid()

    def __list2str(self, datas=[]):
        """
        将传入的list数据转换成 | 划分的字符串
        e.g. ['user1', 'user2'] -> 'user1|user2'
        :param datas:
        :return:
        """
        return "".join([item + "|" for item in datas])[:-1]

    def _get_media_id(self, media_type: str, p_media: Path):
        data = {"file": p_media.open("rb")}
        response = self.api.http_call(
            CORP_API_TYPE["MEDIA_UPLOAD"],
            {"type": media_type, "files": data},
        )

        return response

    def _send(
        self,
        msg_type: str = "",
        data: dict = {},
        media_path: Optional[str] = "",
        **kwargs,
    ):
        """
        新的统一内部发送接口，供不同消息推送接口调用
        :param msg_type:
        :param data:
        :param media_path: 只有需要media id的时候才传入
        :param kwargs:
        :return:
        """
        if not (kwargs.get("touser") or kwargs.get("toparty") or kwargs.get("totag")):
            # 三者均为空，默认发送全体成员
            kwargs["touser"] = ["@all"]

        data["chatid"] = kwargs.get("chatid", "")
        if not data["chatid"]:
            # 不是发送到群聊的消息
            data.update(
                {
                    "touser": self.__list2str(kwargs.get("touser", [])),
                    "toparty": self.__list2str(kwargs.get("toparty", [])),
                    "totag": self.__list2str(kwargs.get("totag", [])),
                    "agentid": self.agentid,
                    "enable_id_trans": kwargs.get("enable_id_trans"),
                    "enable_duplicate_check": kwargs.get("enable_duplicate_check"),
                    "duplicate_check_interval": kwargs.get("duplicate_check_interval"),
                }
            )

        data.update(
            {
                "msgtype": msg_type,
                "safe": kwargs.get("safe", 0),
            }
        )

        media_types = {"image", "voice", "video", "file"}
        if msg_type in media_types:
            media_res = self._get_media_id(msg_type, Path(media_path))
            data[msg_type] = {"media_id": media_res.get("media_id", "")}
        elif msg_type == "mpnews":
            media_res = self._get_media_id(media_type="image", p_media=Path(media_path))
            thumb_media_id = media_res.get("media_id", None)
            data[msg_type]["articles"][0]["thumb_media_id"] = thumb_media_id

        if data["chatid"]:
            return self.api.http_call(CORP_API_TYPE["APP_CHAT_SEND"], data)

        return self.api.http_call(CORP_API_TYPE["MESSAGE_SEND"], data)

    def send_text(self, content: str, **kwargs):
        """
        发送text消息
        :param content: 消息内容，最长不超过2048个字节，超过将
        :param safe: 是否是保密消息，False表示可对外分享，True表示不能分享且内容显示水印，默认为False，下面方法同，不再重复解释
        :param kwargs: touser, toparty, totag
        :return: send result
        """
        if not content:
            logger.error(self.errmsgs["text_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["text_error"]}
        data = {
            "text": {"content": content},
        }
        return self._send(msg_type="text", data=data, **kwargs)

    def send_markdown(self, content: str, **kwargs):
        """
        发送markdown消息
        :param content: markdown文本数据或markdown文件路径
        :return:
        """
        if not content:
            logger.error(self.errmsgs["markdown_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["markdown_error"]}
        if content.endswith(".md"):
            try:
                content = Path(content).read_text()
            except (OSError, FileNotFoundError):
                logger.warning(
                    "你可能正在尝试发送一个markdown文件，但文件并不存在或文件名过长，将直接发送内容."
                )
        data = {
            "markdown": {
                "content": content,
            },
        }
        return self._send(msg_type="markdown", data=data, **kwargs)

    def send_image(self, image_path: str, **kwargs):
        """
        发送图片，支持jpg、png、bmp
        :param image_path: 图片存储路径
        :return:
        """
        if not is_image(image_path):
            logger.error(self.errmsgs["image_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["image_error"]}
        return self._send(msg_type="image", media_path=image_path, **kwargs)

    def send_voice(self, voice_path: str, **kwargs):
        """
        发送语音，2MB，播放长度不超过60s，仅支持AMR格式
        :param voice_path:
        :return:
        """
        if not is_voice(voice_path):
            logger.error(self.errmsgs["voice_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["voice_error"]}
        return self._send(msg_type="voice", media_path=voice_path, **kwargs)

    def send_video(self, video_path: str, **kwargs):
        """
        发送视频
        :param video_path:
        :return:
        """
        if not is_video(video_path):
            logger.error(self.errmsgs["video_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["video_error"]}
        return self._send(msg_type="video", media_path=video_path, **kwargs)

    def send_news(
        self, title: str, desp: Optional[str], url: str, picurl: Optional[str], **kwargs
    ):
        """
        发送图文消息
        :param title: 图文标题，不超过128个字节，超过会自动截断
        :param desp: 图文描述，可选，不超过512个字节，超过会自动截断
        :param url: 跳转链接
        :param picurl: 图片url，支持JPG、PNG格式，较好的效果为大图 1068*455，小图150*150。
        :return:
        """
        if not (title and url):
            logger.error(self.errmsgs["news_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["news_error"]}
        data = {
            "news": {
                "articles": [
                    {"title": title, "description": desp, "url": url, "picurl": picurl}
                ]
            },
        }
        return self._send(msg_type="news", data=data, **kwargs)

    def send_file(self, file_path: str, **kwargs):
        """
        发送文件
        :param file_path:
        :return:
        """
        if not is_file(file_path):
            logger.error(self.errmsgs["file_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["file_error"]}
        return self._send(msg_type="file", media_path=file_path, **kwargs)

    def send_mpnews(
        self,
        title: str,
        image_path: str,
        content: str,
        author: Optional[str],
        content_source_url: Optional[str],
        digest: Optional[str],
        **kwargs,
    ):
        """
        发送mpnews消息
        :param title: 图文标题
        :param image_path: 缩略图所在路径
        :param content: 图文消息内容
        :param author: 作者信息
        :param content_source_url: 点击跳转链接
        :param digest: 图文消息描述
        :param kwargs:
        :return:
        """
        if not (title and image_path and content):
            logger.error(self.errmsgs["mpnews_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["mpnews_error"]}
        data = {
            "mpnews": {
                "articles": [
                    {
                        "title": title,
                        "author": author,
                        "content_source_url": content_source_url,
                        "content": content,
                        "digest": digest,
                    }
                ]
            }
        }
        return self._send(msg_type="mpnews", data=data, media_path=image_path, **kwargs)

    def send_card(self, title: str, description: str, url: str, **kwargs):
        """
        发送卡片消息
        :param title: 标题，不超过128个字节，超过会自动截断
        :param desp: 描述，不超过512个字节，超过会自动截断
        :param url: 点击后跳转的链接
        :param btntxt: 按钮文字。 默认为“详情”， 不超过4个文字，超过自动截断
        :return:
        """
        if not (title and description and url):
            logger.error(self.errmsgs["card_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["card_error"]}
        btntxt = kwargs.get("btntxt", None)
        data = {
            "textcard": {
                "title": title,
                "description": description,
                "url": url,
                "btntxt": btntxt,
            },
        }
        return self._send(msg_type="textcard", data=data, **kwargs)

    def send_miniprogram_notice(self, *args, **kwargs):
        raise NotImplementedError

    def send_template_card(self, template_card, *args, **kwargs):
        data = {"template_card": template_card}

        return self._send(msg_type="template_card", data=data, **kwargs)

    def create_chat(
        self,
        name: Optional[str] = "",
        owner: Optional[str] = "",
        userlist: list = [],
        chatid: Optional[str] = "",
        show_chat: Optional[bool] = False,
    ):
        """
        创建应用群聊
        :param users: 用户id列表，至少2人
        :param name: 群聊名称
        :param owner: 群主id，不指定会随机
        :param chatid:
        :param show_chat: 群聊创建成功后是否发送一条消息让群聊在列表中显示出来（默认发送）
        :return:
        """
        if len(userlist) < 2:
            logger.error(self.errmsgs["create_chat_error"])
            return {"errcode": 404, "errmsg": self.errmsgs["create_chat_error"]}

        data = {
            "name": name,
            "owner": owner,
            "userlist": userlist,
            "chatid": chatid,
        }

        res = self.api.http_call(CORP_API_TYPE["APP_CHAT_CREATE"], data)

        if show_chat and res["errcode"] == 0:
            logger.info("group chat is created")
            content = f"group chat is created. chatid: {res['chatid']}"
            self.send_text(content=content, chatid=res["chatid"])
            return res
        else:
            return res
