"""
pten.keys
~~~~~~~~~~~~

This module implements the keys class for getting keys from local file.

"""

import configparser
import json
import os
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path

from . import DEFAULT_LOG_PATH, logger, setup_logging


class Keys:
    """Keys class for getting keys from local file

    :param keys_filepath: keys 文件路径，缺省 None 时按以下顺序查找：

        1. 显式传入的路径（文件缺失时直接报错，不回退）
        2. 环境变量 ``PTEN_KEYS_FILE``（文件缺失时直接报错，不回退）
        3. 当前目录 ``./pten_keys.ini``
        4. 用户主目录 ``~/.pten/pten_keys.ini``

    token 缓存文件（pten_token.json）与最终解析出的 keys 文件同目录，
    避免全局配置（如 ~/.pten）时 token 散落在各个运行目录。
    """

    # 命名 LLM provider 段前缀，如 [llm:openai]
    LLM_SECTION_PREFIX = "llm:"

    # keys 文件的缺省文件名与查找链使用的环境变量名
    DEFAULT_KEYS_FILENAME = "pten_keys.ini"
    KEYS_FILE_ENV_VAR = "PTEN_KEYS_FILE"

    def __init__(self, keys_filepath=None, *args, **kwargs):
        self.key_cfg = ConfigParser()
        self.keys_filepath = Keys._resolve_keys_filepath(keys_filepath)
        self.TOKEN_PATH = self.keys_filepath.parent / "pten_token.json"
        self.bot_weebhook_key = None
        self.access_tokens = {}
        self.corp_jsapi_ticket = None
        self.corp_jsapi_ticket_expire_time = float("-inf")
        self.app_jsapi_ticket = None
        self.app_jsapi_ticket_expire_time = float("-inf")

        # 根据当前配置文件中的 [globals] log_path 配置日志文件路径
        setup_logging(log_path=self.get_log_path())

        logger.info(f"keys_filepath : {self.keys_filepath}")

        if not self.keys_filepath.is_file():
            logger.error(f"Can not find file {self.keys_filepath}")

    @classmethod
    def _resolve_keys_filepath(cls, keys_filepath):
        """按优先级解析 keys 文件路径，返回实际使用的 Path。

        优先级从高到低：
        1. 显式传入的 keys_filepath（严格：文件缺失时直接报错，不回退）
        2. 环境变量 ``PTEN_KEYS_FILE``（严格：文件缺失时直接报错，不回退）
        3. 当前目录 ``./pten_keys.ini``（探测：不存在则继续找）
        4. 用户主目录 ``~/.pten/pten_keys.ini``（探测）

        后两级均未命中时回落到 ``./pten_keys.ini``，保持旧行为
        （初始化仅告警，取 key 时才抛 FileNotFoundError）。

        显式路径与环境变量里的 ``~`` 会展开为用户主目录。
        """
        if keys_filepath is not None:
            return Path(keys_filepath).expanduser()

        env_value = os.environ.get(cls.KEYS_FILE_ENV_VAR)
        if env_value:
            return Path(env_value).expanduser()

        candidates = [Path(cls.DEFAULT_KEYS_FILENAME)]
        try:
            candidates.append(Path.home() / ".pten" / cls.DEFAULT_KEYS_FILENAME)
        except RuntimeError:
            pass

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        msg = "Can not find keys file, tried: " + ", ".join(str(c) for c in candidates)
        logger.warning(msg)
        return candidates[0]

    def _read_keys_file(self, cfg: ConfigParser, path):
        """读取 ini 文件：优先按 UTF-8 解析，失败时回退系统本地编码。

        utf-8-sig 既剥 BOM又兼容无 BOM 的普通 UTF-8。
        """
        try:
            cfg.read(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            # 兼容以本地编码（如 GBK）写就的历史配置文件
            cfg.clear()
            cfg.read(path)

    def _get_local_keys(self, section: str, options=[]):
        """Get keys from local file
        :param section: Section name of the keys
        :param options: The keys you want to get
        :return: generator of the keys
        """
        if self.keys_filepath.is_file():
            self.key_cfg.clear()
            self._read_keys_file(self.key_cfg, self.keys_filepath)
            try:
                for option in options:
                    yield self.key_cfg.get(section, option)
            except (configparser.NoSectionError, configparser.NoOptionError):
                raise configparser.Error("KeyConfigError")
        else:
            raise FileNotFoundError(f"Can not find file {self.keys_filepath}")

    def get_key(self, section: str, option: str):
        """Get keys from local file
        :param section: Section name of the keys
        :param option: The key you want to get
        :return: key value
        """
        return next(self._get_local_keys(section, [option]))

    def get_keys(self, section: str, options=[]):
        """Get keys from local file
        :param section: Section name of the keys
        :param options: The keys you want to get
        :return: dict of the keys
        """
        res = {}
        for k, v in zip(options, self._get_local_keys(section, options)):
            res.update({k: v})
        return res

    def get_debug_mode(self):
        debug_mode_str = "false"
        try:
            debug_mode_str = self.get_key("globals", "debug_mode")
        except (configparser.Error, FileNotFoundError):
            debug_mode_str = "false"

        debug_mode = debug_mode_str.lower() in ("true", "yes", "on", "1")
        return debug_mode

    def get_log_path(self):
        try:
            return self.get_key("globals", "log_path")
        except (configparser.Error, FileNotFoundError):
            return DEFAULT_LOG_PATH

    def list_llm_providers(self):
        """返回配置文件中所有 [llm:<name>] 命名段的 name 列表（按文件中出现顺序）。"""
        cfg = ConfigParser()
        if self.keys_filepath.is_file():
            self._read_keys_file(cfg, self.keys_filepath)
        return [
            s[len(Keys.LLM_SECTION_PREFIX) :]
            for s in cfg.sections()
            if s.startswith(Keys.LLM_SECTION_PREFIX)
        ]

    def get_proxies(self):
        proxies = None
        try:
            proxies = self.get_keys(section="proxies", options=["http", "https"])
        except (configparser.Error, FileNotFoundError):
            pass

        return proxies

    def get_bot_weebhook_key(self, section="ww"):
        if self.bot_weebhook_key is None:
            key = next(self._get_local_keys(section=section, options=["webhook_key"]))
            self.bot_weebhook_key = key

        return self.bot_weebhook_key

    def get_app_agentid(self):
        return next(self._get_local_keys(section="ww", options=["app_agentid"]))

    def get_contact_sync_secret(self):
        try:
            s = self.get_key("ww", "contact_sync_secret")
        except (configparser.Error, FileNotFoundError):
            logger.warning("Can not find contact_sync_secret in keys ini file")
            s = None
        return s

    def get_fs_receive_id(self):
        """读 [fs] receive_id：飞书应用消息的默认接收者，未配置返回 None"""
        try:
            return self.get_key("fs", "receive_id")
        except (configparser.Error, FileNotFoundError):
            return None

    def get_fs_receive_id_type(self):
        """读 [fs] receive_id_type：默认接收者的 ID 类型，未配置返回 None"""
        try:
            return self.get_key("fs", "receive_id_type")
        except (configparser.Error, FileNotFoundError):
            return None

    @staticmethod
    def load_from_file(file_path: Path, key):
        if not file_path.is_file():
            raise FileNotFoundError(f"Can not find file {file_path}.")

        dict = json.loads(file_path.read_text())
        if key not in dict:
            raise KeyError(f"Can not find token of {key}.")

        return dict[key]

    @staticmethod
    def save_to_file(file_path: Path, key, info):
        token_dict = {}
        if file_path.is_file():
            token_dict = json.loads(file_path.read_text())

        token_dict.update({key: info})
        try:
            file_path.write_text(json.dumps(token_dict))
        except OSError as e:
            # keys 文件所在目录不可写等场景：内存缓存已生效，仅持久化失败
            logger.warning(f"Can not save token cache to {file_path}: {e}")

    def get_access_token(self, token_key):
        now = datetime.now().timestamp()
        token_info = self.access_tokens.get(token_key)
        if token_info and token_info.get("expire_time", float("-inf")) > now:
            return token_info["access_token"]

        token_info = Keys.load_from_file(self.TOKEN_PATH, token_key)
        self.access_tokens[token_key] = token_info
        if token_info.get("expire_time", float("-inf")) < now:
            logger.warning(f"Token of {token_key} is expired.")
            raise Exception("Token expired")

        return token_info["access_token"]

    def save_access_token(self, token_key, access_token, expire=7200):
        """持久化 access token；expire 为有效期秒数，缺省 7200（2 小时）。

        飞书等厂商在 token 响应里返回实际有效期（``expire`` 字段），调用方可
        透传该值，避免平台调整有效期时客户端误判。
        """
        token_info = {
            "access_token": access_token,
            "expire_time": datetime.now().timestamp() + expire,
        }
        self.access_tokens[token_key] = token_info
        Keys.save_to_file(self.TOKEN_PATH, token_key, token_info)

    def get_corp_jsapi_ticket(self, token_key):
        now = datetime.now().timestamp()
        if self.corp_jsapi_ticket_expire_time > now:
            return self.corp_jsapi_ticket

        ticket_key = token_key + "_corp_jsapi_ticket"
        ticket_info = Keys.load_from_file(self.TOKEN_PATH, ticket_key)
        expire_time = ticket_info.get("expire_time", float("-inf"))
        self.corp_jsapi_ticket_expire_time = expire_time
        if expire_time < now:
            logger.warning(f"Ticket of {ticket_key} is expired.")
            raise Exception("Ticket expired")

        self.corp_jsapi_ticket = ticket_info["corp_jsapi_ticket"]
        return self.corp_jsapi_ticket

    def save_corp_jsapi_ticket(self, token_key, corp_jsapi_ticket):
        ticket_key = token_key + "_corp_jsapi_ticket"
        self.corp_jsapi_ticket = corp_jsapi_ticket
        self.corp_jsapi_ticket_expire_time = datetime.now().timestamp() + 7200
        ticket_info = {
            "corp_jsapi_ticket": corp_jsapi_ticket,
            "expire_time": self.corp_jsapi_ticket_expire_time,
        }
        Keys.save_to_file(self.TOKEN_PATH, ticket_key, ticket_info)

    def get_app_jsapi_ticket(self, token_key):
        now = datetime.now().timestamp()
        if self.app_jsapi_ticket_expire_time > now:
            return self.app_jsapi_ticket

        ticket_key = token_key + "_app_jsapi_ticket"
        ticket_info = Keys.load_from_file(self.TOKEN_PATH, ticket_key)
        expire_time = ticket_info.get("expire_time", float("-inf"))
        self.app_jsapi_ticket_expire_time = expire_time
        if expire_time < now:
            logger.warning(f"Ticket of {ticket_key} is expired.")
            raise Exception("Ticket expired")

        self.app_jsapi_ticket = ticket_info["app_jsapi_ticket"]
        return self.app_jsapi_ticket

    def save_app_jsapi_ticket(self, token_key, app_jsapi_ticket):
        ticket_key = token_key + "_app_jsapi_ticket"
        self.app_jsapi_ticket = app_jsapi_ticket
        self.app_jsapi_ticket_expire_time = datetime.now().timestamp() + 7200
        ticket_info = {
            "app_jsapi_ticket": app_jsapi_ticket,
            "expire_time": self.app_jsapi_ticket_expire_time,
        }
        Keys.save_to_file(self.TOKEN_PATH, ticket_key, ticket_info)
