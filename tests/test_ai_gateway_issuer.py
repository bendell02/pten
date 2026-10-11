"""ai_gateway 服务端发证纯逻辑测试（不依赖 fastapi，最小依赖即可跑）。

CredentialIssuer.issue 的解密→查表→加密流程与 load_config 的配置加载，
都不碰 HTTP 层，与 issuer.py「不 import fastapi，便于无 server extras 时
也能单元测试」的设计意图对齐。
"""

import json

import pytest

from pten.wwcrypt import WXBizMsgCrypt
from pten.tools.ai_gateway.issuer import CredentialIssuer, GatewayError, load_config
from pten.tools.ai_gateway.protocol import decrypt_message

# 全局共享测试常量
TOKEN = "shared_msg_token"
AES_KEY = "9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO"
RECEIVE_ID = "shared_receive_id"


def _encrypt_request(client_id=None, nonce="n1"):
    """用共享密钥加密一个取凭证请求，返回 XML 信封。

    client_id 为 None 时请求体为空 dict（走服务端 [client:default] 段）。
    timestamp 由 EncryptMsg 自动取当前时间；服务端不再校验时间窗，
    不会因系统时钟不一致导致取凭证失败。
    """
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    req_obj = {"client_id": client_id} if client_id else {}
    ret, xml = crypt.EncryptMsg(json.dumps(req_obj), nonce)
    assert ret == 0
    return xml


@pytest.fixture()
def issuer():
    """构造一个内存中的 CredentialIssuer（不读 ini）。"""
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    clients = {
        "agent-x": {
            "api_key": "sk-real-xxxxxxxxxxxxwxyz",
            "url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
        }
    }
    return CredentialIssuer(crypt, clients, ttl_days=90)


@pytest.fixture()
def issuer_with_default():
    """含 [client:default] 段的 issuer（所有 agent 共用一组凭证的场景）。"""
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    clients = {
        "default": {
            "api_key": "sk-default-xxxxxxxxxxxxwxyz",
            "url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
        }
    }
    return CredentialIssuer(crypt, clients, ttl_days=90)


# ---- CredentialIssuer.issue 纯逻辑 ----


def test_issue_returns_decryptable_bundle(issuer):
    """成功发证：返回的 XML 能被同密钥解密成正确 bundle。"""
    resp_xml = issuer.issue(_encrypt_request("agent-x"))
    receiver = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    bundle = decrypt_message(receiver, resp_xml)
    assert bundle["client_id"] == "agent-x"
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"
    assert bundle["url"] == "https://api.deepseek.com"
    assert bundle["model"] == "deepseek-v4-flash"
    assert "expire_at" in bundle


def test_issue_unknown_client_raises_404(issuer):
    """未知 client_id 抛 GatewayError(status=404)。"""
    with pytest.raises(GatewayError) as exc:
        issuer.issue(_encrypt_request("unknown"))
    assert exc.value.status == 404


def test_issue_no_client_id_falls_back_to_default(issuer_with_default):
    """请求不带 client_id 时回落 [client:default] 段。"""
    resp_xml = issuer_with_default.issue(_encrypt_request(None))
    receiver = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    bundle = decrypt_message(receiver, resp_xml)
    assert bundle["client_id"] == "default"
    assert bundle["api_key"] == "sk-default-xxxxxxxxxxxxwxyz"


def test_issue_no_client_id_no_default_raises_404(issuer):
    """请求不带 client_id 且服务端无 [client:default] 段 → 404。"""
    with pytest.raises(GatewayError) as exc:
        issuer.issue(_encrypt_request(None))
    assert exc.value.status == 404
    assert exc.value.code == "NO_DEFAULT"


def test_issue_wrong_receive_id_raises_401(issuer):
    """receive_id 不匹配（解密失败）抛 401。"""
    bad = WXBizMsgCrypt(TOKEN, AES_KEY, "other_receive_id")
    ret, xml = bad.EncryptMsg(json.dumps({"client_id": "agent-x"}), "n")
    assert ret == 0
    with pytest.raises(GatewayError) as exc:
        issuer.issue(xml)
    assert exc.value.status == 401


def test_issue_malformed_xml_raises_401(issuer):
    """畸形 XML 信封抛 401，不抛 AttributeError 崩溃。"""
    with pytest.raises(GatewayError) as exc:
        issuer.issue("<xml><NotEncrypt/></xml>")
    assert exc.value.status == 401


def test_issue_logs_masked_api_key(issuer, caplog):
    """发证日志不得出现明文 api_key。"""
    with caplog.at_level("INFO"):
        issuer.issue(_encrypt_request("agent-x"))
    assert "sk-real-xxxxxxxxxxxxwxyz" not in caplog.text


# ---- load_config ----


def test_load_config_reads_example_ini():
    """load_config 从 example ini 构造 issuer。"""
    issuer = load_config("ai_gateway_server_example.ini")
    assert "agent-x" in issuer.clients
    assert issuer.clients["agent-x"]["model"] == "deepseek-v4-flash"
    assert issuer.ttl_days == 90
