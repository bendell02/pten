"""
pten.base_api
~~~~~~~~~~~~

企业微信（wwapi）与飞书（fs_api）API 层共用的 HTTP 调用基础设施。
各厂商模块继承 :class:`AbstractApi`，并通过若干类属性提供配置：基础 URL、
响应字段名、支持的 token 占位符集合、以及表示“token 已过期”的 errcode 集合。
端点定义（``*_API_TYPE`` 字典）与高层子类（``BotApi`` / ``CorpApi`` 等）
仍保留在各厂商模块中。
"""

from . import logger
from .keys import Keys
import json
import requests
from urllib.parse import urlencode


class ApiException(Exception):
    def __init__(self, errCode, errMsg):
        self.errCode = errCode
        self.errMsg = errMsg


class AbstractApi(object):
    """所有厂商 API 客户端的基类。

    子类通过类属性配置行为，并按需重写 token 相关的钩子方法（如 :meth:`get_access_token`）。
    端点定义存放在各子类模块的 ``*_API_TYPE`` 字典中，逻辑名 -> ``[shortUrl, method]``。
    URL 中携带占位符（``ACCESS_TOKEN``、``WEBHOOK_KEY`` 等），:meth:`_append_token`
    会在调用对应 getter 时惰性替换。遇到表示 token 过期的 errcode 时，调用对应的
    ``refresh_*`` 方法并最多重试 3 次。
    """

    BASE_URL = ""  # 基础 URL，如 "https://qyapi.weixin.qq.com"
    RESPONSE_CODE_FIELD = "errcode"
    RESPONSE_MSG_FIELD = "errmsg"
    # 有序：较长/更具体的占位符必须排在它所包含的子串之前
    # （如 SUITE_ACCESS_TOKEN 必须在 ACCESS_TOKEN 之前）。取第一个匹配项。
    TOKEN_PLACEHOLDERS = ()  # (占位符, getter 方法名) 组成的元组
    TOKEN_EXPIRED_CODES = ()  # 表示“token 过期，需刷新后重试”的 errcode 集合

    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None):
        self.keys = keys if keys else Keys(keys_filepath)
        self.DEBUG_MODE = self.keys.get_debug_mode()
        self.proxies = self.keys.get_proxies()

    # -- token 钩子：需要的子类自行重写 --
    def get_access_token(self):
        raise NotImplementedError

    def refresh_access_token(self):
        raise NotImplementedError

    def get_suite_access_token(self):
        raise NotImplementedError

    def refresh_suite_access_token(self):
        raise NotImplementedError

    def get_provider_access_token(self):
        raise NotImplementedError

    def refresh_provider_access_token(self):
        raise NotImplementedError

    def get_bot_webhook_key(self):
        raise NotImplementedError

    # -- 核心分发 --
    def http_call(self, urlType, args=None):
        shortUrl = urlType[0]
        method = urlType[1]
        response = {}
        for retryCnt in range(0, 3):
            if "POST" == method:
                url = self._make_url(shortUrl)
                response = self._http_post(url, args)
            elif "GET" == method:
                url = self._make_url(shortUrl)
                url = self._append_args(url, args)
                response = self._http_get(url)
            elif "POST_FILE" == method:
                url = self._make_url(shortUrl)
                response = self._post_file(url, args)
            else:
                raise ApiException(-1, "unknown method type")

            # 检查 token 是否过期
            if self._token_expired(response.get(self.RESPONSE_CODE_FIELD)):
                self._refresh_token(shortUrl)
                retryCnt += 1
                continue
            else:
                break

        return self._check_response(response)

    # -- URL 构造 --
    @staticmethod
    def _append_args(url, args):
        if args is None:
            return url

        for key, value in args.items():
            if "?" in url:
                url += "&" + key + "=" + value
            else:
                url += "?" + key + "=" + value
        return url

    @classmethod
    def _make_url(cls, shortUrl):
        if shortUrl[0] == "/":
            return cls.BASE_URL + shortUrl
        else:
            return cls.BASE_URL + "/" + shortUrl

    def _append_token(self, url):
        for placeholder, getter_name in self.TOKEN_PLACEHOLDERS:
            if placeholder in url:
                return url.replace(placeholder, getattr(self, getter_name)())
        return url

    # -- HTTP 方法 --
    def _debug_url(self, url):
        """厂商特定的调试查询参数钩子。默认不做任何处理。"""
        return url

    def _http_post(self, url, args):
        realUrl = self._append_token(url)

        if self.DEBUG_MODE is True:
            realUrl = self._debug_url(realUrl)
            query_string = urlencode(args)
            full_url = f"{realUrl}?{query_string}"
            logger.debug(full_url)

        return requests.post(
            realUrl,
            data=json.dumps(args, ensure_ascii=False).encode("utf-8"),
            proxies=self.proxies,
        ).json()

    def _http_get(self, url):
        realUrl = self._append_token(url)

        if self.DEBUG_MODE is True:
            realUrl = self._debug_url(realUrl)
            logger.debug(realUrl)

        return requests.get(realUrl, proxies=self.proxies).json()

    def _post_file(self, url, args):
        realUrl = self._append_token(url)

        type = args.get("type", None)
        files = args.get("files", None)
        if type is None or files is None:
            raise ApiException(-1, "type is None or file is None")

        realUrl = self._append_args(realUrl, {"type": type})

        return requests.post(realUrl, files=files, proxies=self.proxies).json()

    # -- 响应处理 --
    def _check_response(self, response):
        errCode = response.get(self.RESPONSE_CODE_FIELD)
        errMsg = response.get(self.RESPONSE_MSG_FIELD)

        if errCode == 0:
            return response
        else:
            raise ApiException(errCode, errMsg)

    def _token_expired(self, errCode):
        return errCode in self.TOKEN_EXPIRED_CODES

    def _refresh_token(self, url):
        for placeholder, getter_name in self.TOKEN_PLACEHOLDERS:
            refresh_name = getter_name.replace("get_", "refresh_")
            if placeholder in url and hasattr(self, refresh_name):
                getattr(self, refresh_name)()
                return
