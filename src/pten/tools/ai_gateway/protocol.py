"""pten.tools.ai_gateway.protocol
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

凭证网关传输协议的无依赖叶模块：信封加解密与密钥屏蔽。

信封即 ``WXBizMsgCrypt.EncryptMsg`` 产出的整段 XML，含 ``Encrypt`` /
``MsgSignature`` / ``TimeStamp`` / ``Nonce`` 四个标签，作为 HTTP POST body
自包含传输。本模块把「parse 信封四字段 + 验签解密 + JSON 序列化」收敛为
:func:`decrypt_message` / :func:`encrypt_message` 两个函数，调用方只管
dict <-> XML 信封，不再各自拼装加解密步骤。

本模块不 import ``wwcrypt``（``crypt`` 参数是 duck-typed 的
``WXBizMsgCrypt``），保持纯 stdlib 叶模块，可被 server / client 两侧复用。
"""

import json
import random
import xml.etree.ElementTree as ET
from typing import NamedTuple

__all__ = [
    "decrypt_message",
    "encrypt_message",
    "Envelope",
    "mask_api_key",
    "parse_envelope",
    "ProtocolError",
]


class ProtocolError(Exception):
    """信封加解密协议错误，携带 (code, msg) 供调用方映射为各自的业务错误。"""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code
        self.msg = msg


class Envelope(NamedTuple):
    """信封四字段，与 ``WXBizMsgCrypt`` 的 XML 模板一一对应。"""

    encrypt: str
    msg_signature: str
    timestamp: str
    nonce: str


# 信封中需要提取的标签名（顺序与 Envelope 字段一致）
_ENVELOPE_TAGS = ("Encrypt", "MsgSignature", "TimeStamp", "Nonce")


def parse_envelope(xml_body: str) -> Envelope:
    """从 XML 信封中解析出四字段。

    :param xml_body: ``EncryptMsg`` 产出的整段 XML 字符串
    :return: :class:`Envelope`
    :raises ValueError: XML 解析失败或任一必需标签缺失
    """
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError as e:
        raise ValueError(f"信封 XML 解析失败: {e}")

    values = []
    for tag in _ENVELOPE_TAGS:
        node = root.find(tag)
        if node is None or node.text is None:
            raise ValueError(f"信封缺少字段: {tag}")
        values.append(node.text)
    return Envelope(*values)


def decrypt_message(crypt, xml: str) -> dict:
    """验签解密一个 XML 信封，返回其中的 JSON dict。

    :param crypt: ``WXBizMsgCrypt`` 实例（duck-typed）
    :param xml: 信封 XML（POST body）
    :return: 信封内的 JSON dict
    :raises ProtocolError: 信封解析失败、验签解密失败或明文不是合法 JSON
    """
    try:
        env = parse_envelope(xml)
    except ValueError as e:
        raise ProtocolError("BAD_ENVELOPE", str(e))
    ret, plain = crypt.DecryptMsg(xml, env.msg_signature, env.timestamp, env.nonce)
    if ret != 0:
        raise ProtocolError("DECRYPT_FAILED", f"解密失败 errcode={ret}")
    try:
        return json.loads(plain.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProtocolError("BAD_MESSAGE", f"明文不是合法 JSON: {e}")


def encrypt_message(crypt, obj: dict) -> str:
    """把 dict 序列化为 JSON 并加密成 XML 信封。

    :param crypt: ``WXBizMsgCrypt`` 实例（duck-typed）
    :param obj: 待加密的 JSON 兼容 dict
    :return: ``EncryptMsg`` 产出的信封 XML 字符串
    :raises ProtocolError: JSON 序列化或加密失败
    """
    try:
        plain = json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        raise ProtocolError("BAD_MESSAGE", f"对象无法序列化为 JSON: {e}")
    nonce = str(random.randint(1000000000000000, 9999999999999999))
    ret, xml = crypt.EncryptMsg(plain, nonce)
    if ret != 0:
        raise ProtocolError("ENCRYPT_FAILED", f"加密失败 errcode={ret}")
    return xml


def mask_api_key(key: str) -> str:
    """屏蔽 api_key：保留前 4 + 后 4，中间用 ``...`` 占位。

    长度不足或为空时返回 ``"***"``，避免短 key 泄露更多字符。
    """
    if not key or len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
