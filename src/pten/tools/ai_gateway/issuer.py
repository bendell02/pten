"""pten.tools.ai_gateway.issuer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

服务端发证纯逻辑：解密请求 → 查表 → 构造响应明文 → 加密。

不 import fastapi，便于无 server extras 时也能单元测试。
"""

import configparser
from datetime import datetime, timedelta, timezone

from ... import logger
from ...wwcrypt import WXBizMsgCrypt
from .protocol import ProtocolError, decrypt_message, encrypt_message, mask_api_key

__all__ = ["CredentialIssuer", "GatewayError", "load_config"]

# 客户端配置段前缀，如 [client:agent-x]
_CLIENT_SECTION_PREFIX = "client:"
# 服务端配置段名
_GATEWAY_SECTION = "gateway"


class GatewayError(Exception):
    """网关业务错误，携带 (code, msg, status) 供 HTTP 层映射状态码。"""

    def __init__(self, code, msg, status=400):
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.status = status


class CredentialIssuer:
    """凭证发证器：持有共享密钥与客户端表，发证流程不碰 HTTP。

    :param crypt: 共享的 :class:`WXBizMsgCrypt`（全网关一套密钥材料）
    :param clients: ``{client_id: {api_key, url, model}}`` 客户端凭证表
    :param ttl_days: 下发的 ``expire_at`` 有效期天数
    """

    def __init__(self, crypt, clients, ttl_days):
        self.crypt = crypt
        self.clients = clients
        self.ttl_days = ttl_days

    def issue(self, request_xml):
        """处理一个取凭证请求，返回加密响应 XML。

        :param request_xml: 请求信封 XML（POST body）
        :return: 加密响应 XML 字符串
        :raises GatewayError: 任一校验失败
        """
        # 1. 验签解密请求
        try:
            req = decrypt_message(self.crypt, request_xml)
        except ProtocolError as e:
            raise GatewayError(e.code, e.msg, 401)

        # 2. 取 client_id（可选）：缺失时回落 [default] 段
        client_id = req.get("client_id")
        client = self.clients.get(client_id)
        if client is None:
            # 显式带 client_id 但查不到 → 404；否则若 default 也不存在才报缺配置
            if client_id:
                raise GatewayError("UNKNOWN_CLIENT", f"未知客户端: {client_id}", 404)
            default = self.clients.get("default")
            if default is None:
                raise GatewayError(
                    "NO_DEFAULT",
                    "请求未带 client_id 且服务端无 [client:default] 段",
                    404,
                )
            client = default

        # 3. 构造响应 bundle（expire_at 由网关 now + ttl_days 生成）
        expire_at = (
            datetime.now(timezone.utc) + timedelta(days=self.ttl_days)
        ).isoformat()
        resp_bundle = {
            "client_id": client_id or "default",
            "api_key": client["api_key"],
            "url": client["url"],
            "model": client["model"],
            "expire_at": expire_at,
        }

        # 4. 加密响应
        try:
            resp_xml = encrypt_message(self.crypt, resp_bundle)
        except ProtocolError as e:
            raise GatewayError(e.code, e.msg, 500)

        issued_id = client_id or "default"
        info = f"issued credentials for client_id={issued_id}, api_key={mask_api_key(client['api_key'])}"
        logger.info(info)
        return resp_xml


def load_config(ini_path):
    """从服务端 ini 构造 :class:`CredentialIssuer`。

    :param ini_path: 服务端配置文件路径
    :return: :class:`CredentialIssuer`
    :raises GatewayError: 配置缺失或非法时抛 status=500
    """
    cfg = configparser.ConfigParser()
    try:
        cfg.read(ini_path, encoding="utf-8-sig")
    except (configparser.Error, OSError) as e:
        raise GatewayError("CONFIG_ERROR", f"读取配置失败: {e}", 500)

    if not cfg.has_section(_GATEWAY_SECTION):
        raise GatewayError("CONFIG_ERROR", f"配置缺少 [{_GATEWAY_SECTION}] 段", 500)
    gw = cfg[_GATEWAY_SECTION]
    try:
        token = gw["token"]
        aes_key = gw["aes_key"]
        receive_id = gw["receive_id"]
        ttl_days = int(gw.get("ttl_days", 90))
    except KeyError as e:
        raise GatewayError("CONFIG_ERROR", f"[{_GATEWAY_SECTION}] 缺字段: {e}", 500)
    except ValueError as e:
        raise GatewayError("CONFIG_ERROR", f"[{_GATEWAY_SECTION}] 字段非整数: {e}", 500)

    clients = {}
    for section in cfg.sections():
        if not section.startswith(_CLIENT_SECTION_PREFIX):
            continue
        name = section[len(_CLIENT_SECTION_PREFIX) :]
        try:
            clients[name] = {
                "api_key": cfg[section]["api_key"],
                "url": cfg[section]["url"],
                "model": cfg[section]["model"],
            }
        except KeyError as e:
            raise GatewayError("CONFIG_ERROR", f"[{section}] 缺字段: {e}", 500)

    crypt = WXBizMsgCrypt(token, aes_key, receive_id)
    return CredentialIssuer(crypt, clients, ttl_days)
