"""
pten.keys
~~~~~~~~~~~~

This module implements the keys class for getting keys from local file.

"""

from . import logger, setup_logging, DEFAULT_LOG_PATH
import configparser
from configparser import ConfigParser
from datetime import datetime
import json
from pathlib import Path


class Keys:
    """Keys class for getting keys from local file

    :param keys_filepath: The path of the keys file. Default is "pten_keys.ini"
    """

    # 命名 LLM provider 段前缀，如 [llm:openai]
    LLM_SECTION_PREFIX = "llm:"

    def __init__(self, keys_filepath="pten_keys.ini", *args, **kwargs):
        self.key_cfg = ConfigParser()
        self.keys_filepath = Path(keys_filepath)
        self.TOKEN_PATH = Path("pten_token.json")
        self.bot_weebhook_key = None
        self.access_token = None
        self.access_token_expire_time = float("-inf")
        self.corp_jsapi_ticket = None
        self.corp_jsapi_ticket_expire_time = float("-inf")
        self.app_jsapi_ticket = None
        self.app_jsapi_ticket_expire_time = float("-inf")

        # 根据当前配置文件中的 [globals] log_path 配置日志文件路径
        setup_logging(log_path=self.get_log_path())

        logger.info(f"keys_filepath : {self.keys_filepath}")

        if not self.keys_filepath.is_file():
            logger.error(f"Can not find file {self.keys_filepath}")

    def _get_local_keys(self, section: str, options=[]):
        """Get keys from local file
        :param section: Section name of the keys
        :param options: The keys you want to get
        :return: generator of the keys
        """
        if self.keys_filepath.is_file():
            self.key_cfg.clear()
            self.key_cfg.read(self.keys_filepath)
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
            cfg.read(self.keys_filepath)
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
        except StopIteration:
            logger.warning("Can not find contact_sync_secret in keys ini file")
            s = None
        return s

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
        file_path.write_text(json.dumps(token_dict))

    def get_access_token(self, token_key):
        if self.access_token_expire_time > datetime.now().timestamp():
            return self.access_token

        token_info = Keys.load_from_file(self.TOKEN_PATH, token_key)
        self.access_token_expire_time = token_info.get("expire_time", float("-inf"))
        if self.access_token_expire_time < datetime.now().timestamp():
            logger.warning(f"Token of {token_key} is expired.")
            raise Exception("Token expired")

        self.access_token = token_info["access_token"]
        return self.access_token

    def save_access_token(self, token_key, access_token):
        self.access_token = access_token
        self.access_token_expire_time = datetime.now().timestamp() + 7200
        token_info = {
            "access_token": access_token,
            "expire_time": self.access_token_expire_time,
        }
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
