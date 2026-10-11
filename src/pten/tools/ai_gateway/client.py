"""pten.tools.ai_gateway.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

凭证网关客户端：向服务端取 LLM 凭证三元组（api_key/url/model + expire_at），
本地缓存（内存 + 磁盘），网关不可达时降级到未过期缓存。

agent 拿到凭证后直连 LLM provider，不经网关转发流量。
"""

import configparser
from datetime import datetime

import requests
from openai import OpenAI

from ... import logger
from ...base_api import make_token_key
from ...keys import Keys
from ...wwcrypt import WXBizMsgCrypt
from .protocol import ProtocolError, decrypt_message, encrypt_message, mask_api_key

__all__ = ["AIGatewayClient", "AIGatewayError", "AIGatewayLLM"]

# 客户端配置段名
_SECTION = "ai_gateway"
# 凭证缓存的默认文件名（落在 keys 文件同目录）
_CACHE_FILENAME = "ai_gateway_cache.json"
# 请求超时（秒）
_REQUEST_TIMEOUT = 10


class AIGatewayError(Exception):
    """客户端业务错误，携带 (code, msg)。"""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


class _GatewayUnavailable(Exception):
    """网关不可达（网络错 / 5xx）的内部信号，触发缓存降级。"""


class AIGatewayClient:
    """凭证网关客户端：取三元组 + 缓存降级。

    配置解析顺序（与 ``jev.Jev`` / ``notice.LLM`` 一致）：显式参数 > ``[ai_gateway]`` 段。

    :param gateway_url: 网关 ``/credentials`` 端点 URL
    :param client_id: agent 身份标识
    :param token: 共享签名 token（与服务端一致）
    :param aes_key: 共享 EncodingAESKey（与服务端一致）
    :param receive_id: 共享 receive_id（与服务端一致）
    :param keys_filepath: 参数未传时从此文件读配置
    :param keys: 共享的 :class:`Keys` 实例，传入时忽略 keys_filepath
    """

    def __init__(
        self,
        gateway_url=None,
        client_id=None,
        token=None,
        aes_key=None,
        receive_id=None,
        keys_filepath=None,
        keys=None,
    ):
        self.keys = keys if keys else Keys(keys_filepath)

        self.gateway_url = gateway_url or self._get_config("gateway_url")
        # client_id 可选：缺失时请求不带 client_id，网关回落 [client:default] 段
        self.client_id = client_id or self._get_config("client_id")
        self.token = token or self._get_config("token")
        self.aes_key = aes_key or self._get_config("aes_key")
        self.receive_id = receive_id or self._get_config("receive_id")

        missing = [
            name
            for name, val in (
                ("gateway_url", self.gateway_url),
                ("token", self.token),
                ("aes_key", self.aes_key),
                ("receive_id", self.receive_id),
            )
            if not val
        ]
        if missing:
            raise ValueError(self._missing_config_error(missing))

        self.crypt = WXBizMsgCrypt(self.token, self.aes_key, self.receive_id)
        # 缓存文件与 keys 文件同目录，避免散落到 CWD
        self.cache_path = self.keys.keys_filepath.parent / _CACHE_FILENAME
        # 缓存键用 sha1(client_id)，缺省时按 "default" 键控，避免明文落盘
        self._cache_key = make_token_key("gw_", self.client_id or "default")
        self._memory_bundle = None

    def _get_config(self, option, section=_SECTION):
        """读指定段的某个键，段或键不存在时返回 None（不抛错）。"""
        try:
            return self.keys.get_key(section, option)
        except (configparser.Error, FileNotFoundError):
            return None

    def _missing_config_error(self, missing):
        """配置不全时的报错信息。"""
        file_hint = ""
        if not self.keys.keys_filepath.is_file():
            file_hint = f"（注意：配置文件 {self.keys.keys_filepath} 不存在）"
        msg = f"ai_gateway 配置不全，缺少: {missing}。请在 [ai_gateway] 段配置，或直接传入对应参数。{file_hint}"
        return msg

    def get_credentials(self, force_refresh=False):
        """取 LLM 凭证 bundle。

        :param force_refresh: True 时强制向网关刷新，忽略内存缓存
        :return: ``{client_id, api_key, url, model, expire_at}``
        :raises AIGatewayError: 网关返回 4xx、解密失败，或网关不可达且无有效缓存
        """
        # 内存缓存未过期且不强制刷新 → 直接返回
        if (
            not force_refresh
            and self._memory_bundle
            and not self._is_expired(self._memory_bundle)
        ):
            return self._memory_bundle

        try:
            bundle = self._fetch()
        except _GatewayUnavailable as e:
            # 网关不可达：降级到未过期缓存（内存优先，其次磁盘）
            cached = self._fallback_cache()
            if cached:
                warn = f"网关不可达，降级使用未过期缓存: client_id={cached.get('client_id')} ({e})"
                logger.warning(warn)
                self._memory_bundle = cached
                return cached
            raise AIGatewayError("GATEWAY_UNAVAILABLE", str(e))

        # 成功：写内存 + 磁盘
        self._memory_bundle = bundle
        self._save_cache(bundle)
        info = f"got credentials client_id={bundle.get('client_id')}, api_key={mask_api_key(bundle.get('api_key', ''))}"
        logger.info(info)
        return bundle

    def _fetch(self):
        """向网关请求并解密响应，返回 bundle dict。

        :raises _GatewayUnavailable: 网络错或 5xx
        :raises AIGatewayError: 4xx 或解密失败
        """
        # client_id 有值才带上；缺失时请求体为空 dict，网关回落 [client:default]
        req_obj = {"client_id": self.client_id} if self.client_id else {}
        try:
            req_xml = encrypt_message(self.crypt, req_obj)
        except ProtocolError as e:
            raise AIGatewayError(e.code, e.msg)

        try:
            resp = requests.post(
                self.gateway_url,
                data=req_xml,
                headers={"Content-Type": "application/xml"},
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            raise _GatewayUnavailable(str(e))

        if resp.status_code >= 500:
            raise _GatewayUnavailable(f"网关返回 {resp.status_code}")

        if resp.status_code != 200:
            # 4xx：明文 JSON 错误，直接抛，不降级
            try:
                body = resp.json()
            except ValueError:
                body = {"code": "HTTP_ERROR", "msg": f"HTTP {resp.status_code}"}
            raise AIGatewayError(body.get("code", "HTTP_ERROR"), body.get("msg", ""))

        # 200：验签解密响应信封
        try:
            return decrypt_message(self.crypt, resp.text)
        except ProtocolError as e:
            raise AIGatewayError(e.code, e.msg)

    def _is_expired(self, bundle):
        """判断 bundle 是否过期。

        expire_at 为 ISO8601（含时区）；解析失败或缺失视为已过期。
        比较时用 expire_at 的时区构造 now，兼容 aware/naive。
        """
        exp_str = bundle.get("expire_at") if bundle else None
        if not exp_str:
            return True
        try:
            exp = datetime.fromisoformat(exp_str)
        except ValueError:
            return True
        now = datetime.now(exp.tzinfo)
        return now >= exp

    def _save_cache(self, bundle):
        """把 bundle 持久化到磁盘缓存文件。

        持久化失败（目录不可写、旧缓存文件损坏导致 merge 读取失败等）只告警，
        不影响调用——内存缓存已生效。
        """
        try:
            Keys.save_to_file(self.cache_path, self._cache_key, bundle)
        except Exception as e:
            warn = f"缓存持久化失败，内存缓存仍生效: {e}"
            logger.warning(warn)

    def _load_cache(self):
        """读磁盘缓存 bundle，文件缺失/键缺失/文件损坏均返回 None。"""
        try:
            return Keys.load_from_file(self.cache_path, self._cache_key)
        except (FileNotFoundError, KeyError, ValueError):
            return None

    def _fallback_cache(self):
        """网关不可达时的降级缓存：内存优先，其次磁盘，均须未过期。

        :return: 未过期的 bundle，或 None
        """
        if self._memory_bundle and not self._is_expired(self._memory_bundle):
            return self._memory_bundle
        cached = self._load_cache()
        if cached and not self._is_expired(cached):
            return cached
        return None


class AIGatewayLLM:
    """OpenAI 兼容的 LLM 便捷层：构造时自动取凭证，agent 一行调用。

    不继承 :class:`pten.notice.LLM`，避免卷入它的配置解析；只复刻
    ``get_completion`` 接口，用法与 ``notice.LLM`` 一致。

    :param client: 已构造的 :class:`AIGatewayClient`；为 None 时用
        ``client_kwargs`` 新建一个
    :param system_prompt: 系统提示词，默认 :attr:`DEFAULT_SYSTEM_PROMPT`
    :param client_kwargs: 透传给 :class:`AIGatewayClient` 的构造参数
        （如 ``keys`` / ``keys_filepath`` / 显式凭证等）
    """

    DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant"

    def __init__(
        self, client=None, system_prompt=DEFAULT_SYSTEM_PROMPT, **client_kwargs
    ):
        self.client = client or AIGatewayClient(**client_kwargs)
        bundle = self.client.get_credentials()
        self.model = bundle["model"]
        self.openai = OpenAI(api_key=bundle["api_key"], base_url=bundle["url"])
        self.system_prompt = system_prompt

    def get_completion(self, prompt):
        """问一个问题，返回模型回复文本。"""
        logger.info(f"AIGatewayLLM prompt: {prompt}")
        response = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        return response.choices[0].message.content
