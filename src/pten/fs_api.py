"""
pten.fs_api
~~~~~~~~~~~~

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
    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None):
        self.keys = keys if keys else Keys(keys_filepath)
        self.DEBUG_MODE = self.keys.get_debug_mode()
        self.proxies = self.keys.get_proxies()

    def get_bot_webhook_key(self):
        raise NotImplementedError

    def http_call(self, urlType, args=None):
        shortUrl = urlType[0]
        method = urlType[1]
        response = {}
        for retryCnt in range(0, 3):
            if "POST" == method:
                url = self.__make_url(shortUrl)
                response = self.__http_post(url, args)
            else:
                raise ApiException(-1, "unknown method type")

            # check if token expired
            if self.__token_expired(response.get("StatusCode")):
                self.__refresh_token(shortUrl)
                retryCnt += 1
                continue
            else:
                break

        return self.__check_response(response)

    @staticmethod
    def __append_args(url, args):
        if args is None:
            return url

        for key, value in args.items():
            if "?" in url:
                url += "&" + key + "=" + value
            else:
                url += "?" + key + "=" + value
        return url

    @staticmethod
    def __make_url(shortUrl):
        base = "https://open.feishu.cn/open-apis"
        if shortUrl[0] == "/":
            return base + shortUrl
        else:
            return base + "/" + shortUrl

    def __appendToken(self, url):
        if "WEBHOOK_KEY" in url:
            return url.replace("WEBHOOK_KEY", self.get_bot_webhook_key())
        else:
            return url

    def __http_post(self, url, args):
        realUrl = self.__appendToken(url)

        if self.DEBUG_MODE is True:
            query_string = urlencode(args)
            full_url = f"{realUrl}?{query_string}"
            logger.debug(full_url)

        return requests.post(
            realUrl,
            data=json.dumps(args, ensure_ascii=False).encode("utf-8"),
            proxies=self.proxies,
        ).json()

    @staticmethod
    def __check_response(response):
        errCode = response.get("code")
        errMsg = response.get("msg")

        if errCode == 0:
            return response
        else:
            raise ApiException(errCode, errMsg)

    @staticmethod
    def __token_expired(errCode):
        return False  # TODO

    def __refresh_token(self, url):
        pass  # TODO


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
