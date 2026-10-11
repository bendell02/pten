"""ai_gateway 服务端 FastAPI HTTP 层测试（需 pten[ai_gateway] extras）。

未安装 fastapi 时整个文件自动 skip，不影响 issuer 纯逻辑测试与其余测试。
"""

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from pten.wwcrypt import WXBizMsgCrypt
from pten.tools.ai_gateway.protocol import decrypt_message
from pten.tools.ai_gateway.server import create_app

# 全局共享测试常量
TOKEN = "shared_msg_token"
AES_KEY = "9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO"
RECEIVE_ID = "shared_receive_id"


def _http_client():
    """基于 example ini 构造一个 TestClient。"""
    return TestClient(create_app("ai_gateway_server_example.ini"))


def _encrypt_request_xml(client_id):
    """用共享密钥加密取凭证请求。"""
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    ret, xml = crypt.EncryptMsg(json.dumps({"client_id": client_id}), "n")
    assert ret == 0
    return xml


def test_endpoint_returns_encrypted_bundle():
    """POST /credentials 成功返回加密信封，可解密成正确 bundle。"""
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    resp = _http_client().post("/credentials", content=_encrypt_request_xml("agent-x"))
    assert resp.status_code == 200
    bundle = decrypt_message(crypt, resp.text)
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


def test_endpoint_unknown_client_404():
    """未知 client_id 返回 404 + 明文 JSON 错误。"""
    resp = _http_client().post("/credentials", content=_encrypt_request_xml("ghost"))
    assert resp.status_code == 404
    assert resp.json()["code"] == "UNKNOWN_CLIENT"


def test_endpoint_malformed_body_401():
    """畸形 body 返回 401。"""
    resp = _http_client().post("/credentials", content="<xml><x/></xml>")
    assert resp.status_code == 401


def test_endpoint_non_utf8_body_400():
    """非 UTF-8 字节返回 400 而非 500。"""
    resp = _http_client().post("/credentials", content=b"\xff\xfe\x00bad")
    assert resp.status_code == 400
    assert resp.json()["code"] == "BAD_ENCODING"


# ---- 配置热重载 ----


def _write_server_ini(
    path, api_key="sk-real-xxxxxxxxxxxxwxyz", model="deepseek-v4-flash"
):
    """写一份服务端 ini 到 path。"""
    path.write_text(
        "[gateway]\n"
        f"token={TOKEN}\naes_key={AES_KEY}\nreceive_id={RECEIVE_ID}\n"
        "ttl_days=90\n\n"
        "[client:agent-x]\n"
        f"api_key={api_key}\nurl=https://api.deepseek.com\nmodel={model}\n",
        encoding="utf-8",
    )


def test_config_hot_reload_picks_up_changes(tmp_path):
    """改 ini 后下一个请求即时拿到新配置。"""
    ini = tmp_path / "server.ini"
    _write_server_ini(ini, model="deepseek-v4-flash")
    client = TestClient(create_app(str(ini)))

    # 第一次请求：拿到旧 model
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    resp = client.post("/credentials", content=_encrypt_request_xml("agent-x"))
    bundle = decrypt_message(crypt, resp.text)
    assert bundle["model"] == "deepseek-v4-flash"

    # 改 ini（确保 mtime 变化，显式等一下避开文件系统 mtime 精度）
    import time as _time

    _time.sleep(0.01)
    _write_server_ini(ini, model="deepseek-v4-pro")

    # 第二次请求：拿到新 model，无需重启
    resp = client.post("/credentials", content=_encrypt_request_xml("agent-x"))
    bundle = decrypt_message(crypt, resp.text)
    assert bundle["model"] == "deepseek-v4-pro"


def test_config_hot_reload_bad_ini_keeps_old(tmp_path):
    """ini 改坏时保留旧配置继续服务，不抛 500 崩溃。"""
    ini = tmp_path / "server.ini"
    _write_server_ini(ini)
    client = TestClient(create_app(str(ini)))

    import time as _time

    _time.sleep(0.01)
    # 写坏 ini：删掉 [gateway] 段，load_config 会抛
    ini.write_text("[client:agent-x]\napi_key=x\nurl=y\nmodel=z\n", encoding="utf-8")

    # 请求仍应成功（用旧配置），返回 200
    resp = client.post("/credentials", content=_encrypt_request_xml("agent-x"))
    assert resp.status_code == 200


def test_config_no_change_no_reload(tmp_path):
    """ini 未变化时 issuer 实例不替换（未重载）。"""
    ini = tmp_path / "server.ini"
    _write_server_ini(ini)
    app = create_app(str(ini))
    client = TestClient(app)
    issuer_before = app.state.issuer
    client.post("/credentials", content=_encrypt_request_xml("agent-x"))
    client.post("/credentials", content=_encrypt_request_xml("agent-x"))
    # ini 没变，issuer 实例未被替换
    assert app.state.issuer is issuer_before
