"""
pten.fs_api
~~~~~~~~~~~~

This module implements the Feishu API.

"""

from . import base_api, logger
from .base_api import make_token_key
from .keys import Keys


def fetch_all_pages(fetch_page, page_size, page_token, default_page_size):
    """自动翻页聚合全部 items，返回与单页响应同形的 dict（items 为全量、has_more=False）。

    供飞书高层封装（fs_bitable / fs_doc）的列表接口共用。
    :param fetch_page: 取一页的回调，形如 ``fetch_page(page_size, page_token) -> 响应 dict``
    :param page_size: 分页大小；未显式指定时取 default_page_size（最小化请求次数）
    :param page_token: 起始分页标记，缺省从头遍历
    :param default_page_size: page_size 未显式指定时的缺省值，取该端点的分页上限
    """
    if page_size is None:
        page_size = default_page_size
    items = []
    while True:
        res = fetch_page(page_size, page_token)
        items.extend(res["data"].get("items", []))
        if not res["data"].get("has_more"):
            break
        next_token = res["data"].get("page_token")
        # has_more=True 但未返回有效的下一页 token（或 token 未变化）时，
        # 继续翻只会重复拉同一页 → 死循环，主动中断
        if not next_token or next_token == page_token:
            break
        page_token = next_token
    # 聚合后构造与单页响应同形的 dict：items 为全量数据，has_more=False 表示
    # 已拉完，total 为实际返回的条数
    return {
        "code": 0,
        "msg": "success",
        "data": {
            "items": items,
            "has_more": False,
            "total": len(items),
        },
    }


def sub_url(url, **mapping):
    """把 URL 里的路径占位符替换为实参。

    供飞书高层封装（fs_bitable / fs_doc）共用，以关键字传「占位符名 → 实参」。
    """
    for placeholder, value in mapping.items():
        url = url.replace(placeholder, value)
    return url


class FsAbstractApi(base_api.AbstractApi):
    """飞书 API 基类，为共享的 HTTP 管道提供厂商配置。

    webhook 类接口无需鉴权（``TOKEN_EXPIRED_CODES`` 为空，token 刷新为no-op）；
    需要鉴权的接口由 :class:`FsCorpApi` 通过 tenant_access_token 接入。
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


class FsBotApi(FsAbstractApi):
    def __init__(self, keys_filepath=None, webhook_key=None, keys: Keys = None):
        super().__init__(keys_filepath, keys=keys)
        if webhook_key is not None:
            self.webhook_key = webhook_key
        else:
            self.webhook_key = self.keys.get_bot_weebhook_key("fs")

    def get_bot_webhook_key(self):
        return self.webhook_key


CORP_API_TYPE = {
    "GET_TENANT_ACCESS_TOKEN": ["auth/v3/tenant_access_token/internal", "POST"],
    "MESSAGE_SEND": ["im/v1/messages?receive_id_type=RECEIVE_ID_TYPE", "POST"],
    # —— 多维表格操作 ——
    "BITABLE_APP_CREATE": ["bitable/v1/apps", "POST"],
    "BITABLE_TABLE_LIST": ["bitable/v1/apps/APP_TOKEN/tables", "GET"],
    "BITABLE_FIELD_LIST": ["bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/fields", "GET"],
    "BITABLE_TABLE_DELETE": ["bitable/v1/apps/APP_TOKEN/tables/TABLE_ID", "DELETE"],
    "BITABLE_TABLE_CREATE": ["bitable/v1/apps/APP_TOKEN/tables", "POST"],
    "BITABLE_RECORD_CREATE": [
        "bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/records",
        "POST",
    ],
    "BITABLE_RECORD_UPDATE": [
        "bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/records/RECORD_ID",
        "PUT",
    ],
    "BITABLE_RECORD_DELETE": [
        "bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/records/RECORD_ID",
        "DELETE",
    ],
    "BITABLE_RECORD_SEARCH": [
        "bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/records/search",
        "POST",
    ],
    # —— 文档（docx）操作 ——
    "DOC_CREATE": ["docx/v1/documents", "POST"],
    "DOC_GET": ["docx/v1/documents/DOCUMENT_ID", "GET"],
    "DOC_RAW_CONTENT": ["docx/v1/documents/DOCUMENT_ID/raw_content", "GET"],
    "DOC_BLOCK_LIST": ["docx/v1/documents/DOCUMENT_ID/blocks", "GET"],
    "DOC_BLOCK_CREATE": [
        "docx/v1/documents/DOCUMENT_ID/blocks/BLOCK_ID/children",
        "POST",
    ],
    "DOC_BLOCK_CREATE_NESTED": [
        "docx/v1/documents/DOCUMENT_ID/blocks/BLOCK_ID/descendant",
        "POST",
    ],
    "DOC_BLOCK_CONVERT": ["docx/v1/documents/blocks/convert", "POST"],
    "DOC_BLOCK_PATCH": ["docx/v1/documents/DOCUMENT_ID/blocks/BLOCK_ID", "PATCH"],
    "DOC_IMAGE_UPLOAD": ["drive/v1/medias/upload_all", "POST_FILE"],
    "DOC_BLOCK_BATCH_DELETE": [
        "docx/v1/documents/DOCUMENT_ID/blocks/BLOCK_ID/children/batch_delete",
        "DELETE_BODY",
    ],
}


class FsCorpApi(FsAbstractApi):
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
        self, keys_filepath=None, app_id=None, app_secret=None, keys: Keys = None
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
            logger.warning(f"{e!s} refreshing access token...")
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
