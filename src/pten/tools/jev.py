"""
pten.tools.jev
~~~~~~~~~~~~~~~~~~~~~

调用 TypeSafe AI 的 jev 模型（System One API）：输入 state 和一组结构化
问题（Choice / Score / Noul），返回代码可直接使用的类型化答案。

https://docs.typesafe.ai/sdk/python
"""

import configparser
import os
import re

import httpx2
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
from typesafe_sdk.constants import DEFAULT_TIMEOUT

from .. import logger
from ..keys import Keys
from ..utils import brief_for_log

__all__ = ["Choice", "Jev", "Noul", "Score"]


class Jev:
    """jev 模型客户端，配置解析顺序：显式参数 > ``[jev]`` 配置段 > 默认值

    与 notice.LLM 的配置思路一致，但 base_url / model 可全部缺省——
    传 None 时交给 SDK 用默认值（https://api.typesafe.ai / jev-latest）；
    只有 api_key 必须有值（显式参数 > ``[jev]`` 段 > ``TYPESAFE_API_KEY``
    环境变量）。

    可选代理支持（部分区域无法直连 typesafe.ai）：显式 ``proxy`` 参数 >
    ``[jev]`` 段 ``proxy`` > 全局 ``[proxies]`` 段（优先 https 键，缺则
    回落 http 键）。解析出代理时经 httpx2 客户端注入；都未配置时不干预
    SDK 默认客户端（此时 httpx 仍会读 HTTP(S)_PROXY 环境变量）。

    :param base_url: API 根地址，缺省用 SDK 默认；需按 TypeSafe OpenAPI
        规范实现（可用于接 OpenRouter 等 AI 网关）
    :param api_key: API key，获取地址 https://typesafe.ai
    :param model: 模型名，缺省用 SDK 默认
    :param proxy: 代理地址，如 http://user:pass@host:8888
    :param keys_filepath: 当参数未直接传入时，从此文件读取配置，缺省
        路径解析见 :class:`pten.keys.Keys`
    :param keys: 共享的 :class:`pten.keys.Keys` 实例，传入时忽略
        keys_filepath 自建实例的逻辑
    """

    def __init__(
        self,
        base_url=None,
        api_key=None,
        model=None,
        proxy=None,
        keys_filepath=None,
        keys=None,
    ):
        self.keys = keys if keys else Keys(keys_filepath)

        # 解析顺序：显式参数 > [jev] 段；base_url/model 允许为 None 透传 SDK 默认
        self.base_url = base_url or self._get_config("base_url")
        logger.info(f"jev base_url: {self.base_url}")
        self.api_key = (
            api_key or self._get_config("api_key") or os.environ.get("TYPESAFE_API_KEY")
        )
        self.model = model or self._get_config("model")
        self.proxy = proxy or self._get_config("proxy") or self._get_global_proxy()

        if not self.api_key:
            raise ValueError(self._missing_api_key_error())

        http_client = None
        if self.proxy:
            http_client = httpx2.Client(proxy=self.proxy, timeout=DEFAULT_TIMEOUT)
            # 代理地址可能内嵌 user:pass，写日志前屏蔽，避免凭证落盘
            masked_proxy = re.sub(r"//.*@", "//***@", self.proxy)
            info = f"jev proxy enabled: {masked_proxy}"
            logger.info(info)

        try:
            self.client = TypeSafeClient(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                http_client=http_client,
            )
        except Exception:
            # SDK 构造会校验 api_key 格式，失败时关闭已建的代理客户端，避免连接池泄漏
            if http_client is not None:
                http_client.close()
            raise

    def _get_config(self, option, section="jev"):
        """读指定段的某个键，段或键不存在时返回 None（不抛错）"""
        try:
            return self.keys.get_key(section, option)
        except (configparser.Error, FileNotFoundError):
            return None

    def _get_global_proxy(self):
        """读全局 [proxies] 段的代理：优先 https 键，缺则回落 http 键

        不用 Keys.get_proxies()：它要求 http/https 两键齐全，任一缺失即
        返回 None，表达不了「只配一个键」的回落场景。
        """
        return self._get_config("https", section="proxies") or self._get_config(
            "http", section="proxies"
        )

    def _missing_api_key_error(self):
        """api_key 缺失时的报错信息：列出三个获取途径，文件缺失时补充提示"""
        file_hint = ""
        if not self.keys.keys_filepath.is_file():
            file_hint = f"（注意：配置文件 {self.keys.keys_filepath} 不存在）"
        msg = f"api_key 不能为空。请传入 api_key 参数，或在配置文件 [jev] 段配置 api_key，或设置 TYPESAFE_API_KEY 环境变量。{file_hint}"
        return msg

    def ask(self, state, questions, **kwargs):
        """问一组结构化问题，返回完整响应（answers / usage / request_id 等）

        :param state: 提供给模型的上下文，str 或(JSON 兼容的) dict / list
        :param questions: 问题集合，键为自定义问题名，值为
            :class:`~typesafe_sdk.Noul` / :class:`~typesafe_sdk.Choice` /
            :class:`~typesafe_sdk.Score`（可从本模块直接导入）
        :param kwargs: 透传给 ``system_one`` 的其它参数，如 model / retry / timeout
        :return: SystemOneResponse，答案在 ``response.answers["问题名"]``，
            取值分别是 ``.noul`` / ``.choice`` / ``.score``
        https://docs.typesafe.ai/sdk/python/usage
        """
        question_names = ", ".join(questions)
        model_for_log = kwargs.get("model") or self.model or "(SDK 默认)"
        info = f"jev ask: model={model_for_log}, state={brief_for_log({'state': state})}, questions=[{question_names}]"
        logger.info(info)
        return self.client.system_one(state, questions, **kwargs)

    def close(self):
        """关闭底层 TypeSafeClient（连带其 httpx2 客户端）"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
