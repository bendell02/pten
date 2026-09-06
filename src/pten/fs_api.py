"""
pten.fs_api
~~~~~~~~~~~~

This module implements the Feishu API.

"""

from . import base_api, logger
from .base_api import ApiException, make_token_key
from .keys import Keys


class AbstractApi(base_api.AbstractApi):
    """飞书 API 基类，为共享的 HTTP 管道提供厂商配置。

    webhook 类接口无需鉴权（``TOKEN_EXPIRED_CODES`` 为空，token 刷新为no-op）；
    需要鉴权的接口由 :class:`CorpApi` 通过 tenant_access_token 接入。
    """

    BASE_URL = "https://open.feishu.cn/open-apis"
    RESPONSE_CODE_FIELD = "code"
    RESPONSE_MSG_FIELD = "msg"
    TOKEN_PLACEHOLDERS = (("WEBHOOK_KEY", "get_bot_webhook_key"),)
    TOKEN_EXPIRED_CODES = ()

    def _get_headers(self, url):
        # 飞书接口要求以 JSON 编码请求体
        return {"Content-Type": "application/json; charset=utf-8"}


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


CORP_API_TYPE = {
    # 自建应用凭证：请求体携带 app_id/app_secret，无需鉴权
    # https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal
    "GET_TENANT_ACCESS_TOKEN": ["auth/v3/tenant_access_token/internal", "POST"],
    # 发消息给用户/群聊；receive_id_type 是查询参数，取值 open_id/user_id/
    # union_id/email/chat_id，由 AppMsgSender 在发送前替换 URL 中的占位符
    # https://open.feishu.cn/document/server-docs/im-v1/message/create
    "MESSAGE_SEND": ["im/v1/messages?receive_id_type=RECEIVE_ID_TYPE", "POST"],
}


class CorpApi(AbstractApi):
    """飞书自建应用 API：管理 tenant_access_token 的获取与刷新。

    飞书的 token 通过``Authorization: Bearer <tenant_access_token>`` 请求头携带（见
    :meth:`_get_headers`）。token 复用 Keys的持久化缓存（pten_token.json），键为 ``fs_<sha1(app_id+app_secret)>``。

    :param app_id: 飞书自建应用 ID，缺省读 [fs] app_id
    :param app_secret: 飞书自建应用密钥，缺省读 [fs] app_secret
    """

    # token 走请求头而非 URL 占位符（见 _get_headers），不使用占位符机制
    TOKEN_PLACEHOLDERS = ()
    # tenant_access_token 不合法(99991661)或已过期(99991663)，刷新后重试
    TOKEN_EXPIRED_CODES = (99991661, 99991663)

    def __init__(
        self,
        keys_filepath="pten_keys.ini",
        app_id=None,
        app_secret=None,
        keys: Keys = None,
    ):
        super().__init__(keys_filepath, keys=keys)
        self.app_id = app_id if app_id else self.keys.get_key("fs", "app_id")
        self.app_secret = (
            app_secret if app_secret else self.keys.get_key("fs", "app_secret")
        )

        self._token_key = make_token_key("fs_", self.app_id, self.app_secret)

    def get_access_token(self):
        try:
            return self.keys.get_access_token(self._token_key)
        except Exception as e:
            logger.warning(f"{str(e)} refreshing access token...")
            return self.refresh_access_token()

    def refresh_access_token(self):
        response = self.http_call(
            CORP_API_TYPE["GET_TENANT_ACCESS_TOKEN"],
            {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            },
        )
        access_token = response.get("tenant_access_token")
        expire = response.get("expire", 7200)
        self.keys.save_access_token(self._token_key, access_token, expire)

        return access_token

    def _get_headers(self, url):
        headers = super()._get_headers(url)
        # 获取 token 的端点本身无需鉴权；其余端点在请求头携带 tenant_access_token
        if CORP_API_TYPE["GET_TENANT_ACCESS_TOKEN"][0] not in url:
            headers["Authorization"] = "Bearer " + self.get_access_token()
        return headers

    def _refresh_token(self, url):
        # 飞书 token 走请求头而非 URL 占位符，base_api 按占位符匹配定位刷新
        # 的方式不适用，这里直接刷新 tenant_access_token
        self.refresh_access_token()
