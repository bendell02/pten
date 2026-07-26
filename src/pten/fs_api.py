"""
pten.fs_api
~~~~~~~~~~~~

"""

from . import logger
from .keys import Keys
from . import base_api
from .base_api import ApiException


class AbstractApi(base_api.AbstractApi):
    """飞书 API 基类，为共享的 HTTP 管道提供厂商配置。

    token 刷新尚未接入（``TOKEN_EXPIRED_CODES`` 为空），因此 ``_token_expired``
    恒返回 False——与原先的 TODO 桩函数行为一致。
    """

    BASE_URL = "https://open.feishu.cn/open-apis"
    RESPONSE_CODE_FIELD = "code"
    RESPONSE_MSG_FIELD = "msg"
    TOKEN_PLACEHOLDERS = (("WEBHOOK_KEY", "get_bot_webhook_key"),)
    TOKEN_EXPIRED_CODES = ()


BOT_API_TYPE = {
    # bot using webhook key. No access_token
    "WEBHOOK_SEND": ["/bot/v2/hook/WEBHOOK_KEY", "POST"],
}


class BotApi(AbstractApi):
    def __init__(
        self, keys_filepath="pten_keys.ini", webhook_key=None, keys: Keys = None
    ):
        super().__init__(keys_filepath, keys=keys)
        if webhook_key is not None:
            self.webhook_key = webhook_key
        else:
            self.webhook_key = self.keys.get_bot_weebhook_key("fs")

    def get_bot_webhook_key(self):
        return self.webhook_key
