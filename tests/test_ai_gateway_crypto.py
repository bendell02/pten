"""ai_gateway 协议层与加解密契约测试（无网络）。"""

import json

import pytest

from pten.wwcrypt import WXBizMsgCrypt
from pten.tools.ai_gateway.protocol import (
    ProtocolError,
    decrypt_message,
    encrypt_message,
    mask_api_key,
    parse_envelope,
)

# 全局共享测试常量（与 plan Global Constraints 一致）
TOKEN = "shared_msg_token"
AES_KEY = "9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO"
RECEIVE_ID = "shared_receive_id"


@pytest.fixture()
def crypt():
    """一个 WXBizMsgCrypt（encrypt_message/decrypt_message 同密钥自往返）。"""
    return WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)


@pytest.fixture()
def crypt_pair():
    """一对共享相同密钥材料的 WXBizMsgCrypt（模拟 client 与 server 两端）。"""
    return (
        WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID),
        WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID),
    )


def test_envelope_roundtrip(crypt_pair):
    """同密钥往返：client 加密 → server 解密还原明文。"""
    sender, receiver = crypt_pair
    plaintext = json.dumps({"client_id": "agent-x"})
    ret, xml = sender.EncryptMsg(plaintext, "12345")
    assert ret == 0

    env = parse_envelope(xml)
    ret2, decrypted = receiver.DecryptMsg(
        xml, env.msg_signature, env.timestamp, env.nonce
    )
    assert ret2 == 0
    assert decrypted.decode("utf-8") == plaintext


def test_tampered_signature_fails(crypt_pair):
    """签名被篡改时解密必须失败（ret != 0）。"""
    sender, receiver = crypt_pair
    ret, xml = sender.EncryptMsg(json.dumps({"client_id": "x"}), "n")
    env = parse_envelope(xml)
    ret2, _ = receiver.DecryptMsg(
        xml, env.msg_signature + "x", env.timestamp, env.nonce
    )
    assert ret2 != 0


def test_mismatched_receive_id_fails():
    """receive_id 不匹配时解密必须失败（Prpcrypt 嵌入并校验 receiveid）。"""
    sender = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    receiver = WXBizMsgCrypt(TOKEN, AES_KEY, "other_receive_id")
    ret, xml = sender.EncryptMsg(json.dumps({"client_id": "x"}), "n")
    env = parse_envelope(xml)
    ret2, _ = receiver.DecryptMsg(
        xml, env.msg_signature, env.timestamp, env.nonce
    )
    assert ret2 != 0


def test_mask_api_key():
    """api_key 屏蔽：保留前 4 + 后 4，过短或空返回 ***。"""
    assert mask_api_key("sk-abcdefgh1234567890wxyz") == "sk-a...wxyz"
    assert mask_api_key("short") == "***"
    assert mask_api_key("") == "***"


# ---- encrypt_message / decrypt_message 高层封装 ----


def test_encrypt_decrypt_message_roundtrip(crypt):
    """encrypt_message 产出的信封能被同密钥的 decrypt_message 还原成原 dict。"""
    obj = {"client_id": "agent-x", "api_key": "sk-xxxxwxyz", "model": "m"}
    xml = encrypt_message(crypt, obj)
    assert decrypt_message(crypt, xml) == obj


def test_decrypt_message_bad_envelope_raises(crypt):
    """畸形 XML 信封抛 ProtocolError(BAD_ENVELOPE)。"""
    with pytest.raises(ProtocolError) as exc:
        decrypt_message(crypt, "<xml><NotEncrypt/></xml>")
    assert exc.value.code == "BAD_ENVELOPE"


def test_decrypt_message_tampered_raises(crypt):
    """信封被篡改抛 ProtocolError(DECRYPT_FAILED)。"""
    xml = encrypt_message(crypt, {"client_id": "x"})
    env = parse_envelope(xml)
    # 把 MsgSignature 的首字符改掉，破坏签名
    tampered = xml.replace(env.msg_signature, env.msg_signature + "x", 1)
    with pytest.raises(ProtocolError) as exc:
        decrypt_message(crypt, tampered)
    assert exc.value.code == "DECRYPT_FAILED"


def test_decrypt_message_mismatched_receive_id_raises():
    """receive_id 不匹配抛 ProtocolError(DECRYPT_FAILED)。"""
    sender = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    receiver = WXBizMsgCrypt(TOKEN, AES_KEY, "other_receive_id")
    xml = encrypt_message(sender, {"client_id": "x"})
    with pytest.raises(ProtocolError) as exc:
        decrypt_message(receiver, xml)
    assert exc.value.code == "DECRYPT_FAILED"

