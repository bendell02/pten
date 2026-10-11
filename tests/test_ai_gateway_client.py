"""ai_gateway 客户端测试（mock requests.post，无网络）。"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

from pten.keys import Keys
from pten.tools.ai_gateway.client import AIGatewayClient, AIGatewayError, AIGatewayLLM
from pten.wwcrypt import WXBizMsgCrypt

# 全局共享测试常量
TOKEN = "shared_msg_token"
AES_KEY = "9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO"
RECEIVE_ID = "shared_receive_id"


@pytest.fixture()
def gw_keys(tmp_path):
    """构造一份含 [ai_gateway] 段的 keys，缓存文件重定向到 tmp_path。"""
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[ai_gateway]\ngateway_url=http://gw/credentials\nclient_id=agent-x\n"
        f"token={TOKEN}\naes_key={AES_KEY}\nreceive_id={RECEIVE_ID}\n",
        encoding="utf-8",
    )
    keys = Keys(str(ini))
    keys.TOKEN_PATH = tmp_path / "pten_token.json"
    return keys


@pytest.fixture()
def gw_keys_no_client_id(tmp_path):
    """不含 client_id 的 keys（走服务端 [client:default] 段的场景）。"""
    ini = tmp_path / "keys.ini"
    ini.write_text(
        "[ai_gateway]\ngateway_url=http://gw/credentials\n"
        f"token={TOKEN}\naes_key={AES_KEY}\nreceive_id={RECEIVE_ID}\n",
        encoding="utf-8",
    )
    keys = Keys(str(ini))
    keys.TOKEN_PATH = tmp_path / "pten_token.json"
    return keys


def _encrypted_response(bundle):
    """用共享密钥加密一个响应 bundle，返回 XML。"""
    crypt = WXBizMsgCrypt(TOKEN, AES_KEY, RECEIVE_ID)
    ret, xml = crypt.EncryptMsg(json.dumps(bundle), "r1")
    assert ret == 0
    return xml


def _ok_response(bundle):
    """构造一个 status=200 的 mock response，body 为加密信封。"""
    mock = MagicMock()
    mock.status_code = 200
    mock.text = _encrypted_response(bundle)
    return mock


# 有效 bundle：90 天后过期
BUNDLE = {
    "client_id": "agent-x",
    "api_key": "sk-real-xxxxxxxxxxxxwxyz",
    "url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
    "expire_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
}


def test_get_credentials_success(mocker, gw_keys):
    """成功取凭证：返回正确 bundle。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys)
    bundle = c.get_credentials()
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"
    assert bundle["model"] == "deepseek-v4-flash"


def test_get_credentials_without_client_id(mocker, gw_keys_no_client_id):
    """不配 client_id 也能取凭证（走服务端 [client:default] 段）。"""
    post = mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys_no_client_id)
    assert c.client_id is None
    bundle = c.get_credentials()
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"
    # 确认请求体不含 client_id
    sent_body = post.call_args.kwargs["data"]
    assert b"client_id" not in sent_body.encode("utf-8")


def test_get_credentials_caches_to_memory(mocker, gw_keys):
    """第二次 get_credentials 走内存缓存，不再请求网络。"""
    post = mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys)
    c.get_credentials()
    c.get_credentials()
    assert post.call_count == 1


def test_get_credentials_degrades_to_unexpired_cache(mocker, gw_keys):
    """网关不可达 + 磁盘缓存未过期 → 降级返回缓存并 warning。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    c = AIGatewayClient(keys=gw_keys)
    c._save_cache(BUNDLE)  # 预置有效磁盘缓存
    bundle = c.get_credentials()
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


def test_get_credentials_raises_when_cache_expired(mocker, gw_keys):
    """网关不可达 + 磁盘缓存已过期 → 抛 AIGatewayError。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    expired = dict(
        BUNDLE, expire_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    )
    c = AIGatewayClient(keys=gw_keys)
    c._save_cache(expired)
    with pytest.raises(AIGatewayError):
        c.get_credentials()


def test_get_credentials_4xx_raises_without_degrade(mocker, gw_keys):
    """4xx 直接抛错，即便有有效缓存也不降级。"""
    mock = MagicMock(status_code=404)
    mock.json.return_value = {"code": "UNKNOWN_CLIENT", "msg": "unknown"}
    mocker.patch("pten.tools.ai_gateway.client.requests.post", return_value=mock)
    c = AIGatewayClient(keys=gw_keys)
    c._save_cache(BUNDLE)  # 即使有缓存，4xx 也不降级
    with pytest.raises(AIGatewayError) as exc:
        c.get_credentials()
    assert exc.value.code == "UNKNOWN_CLIENT"


def test_get_credentials_tampered_response_raises(mocker, gw_keys):
    """HTTP 200 但响应密文被篡改 → 抛 AIGatewayError，不返回垃圾。"""
    mock = MagicMock(
        status_code=200,
        text=(
            "<xml><Encrypt>garbage</Encrypt>"
            "<MsgSignature>x</MsgSignature><TimeStamp>1</TimeStamp>"
            "<Nonce>n</Nonce></xml>"
        ),
    )
    mocker.patch("pten.tools.ai_gateway.client.requests.post", return_value=mock)
    c = AIGatewayClient(keys=gw_keys)
    with pytest.raises(AIGatewayError):
        c.get_credentials()


def test_client_logs_masked_api_key(mocker, gw_keys, caplog):
    """日志中不得出现明文 api_key。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    with caplog.at_level("INFO"):
        AIGatewayClient(keys=gw_keys).get_credentials()
    assert "sk-real-xxxxxxxxxxxxwxyz" not in caplog.text


# ---- 5xx 降级 / force_refresh / 磁盘往返 / 损坏缓存健壮性 ----


def test_get_credentials_5xx_degrades_to_cache(mocker, gw_keys):
    """网关返回 5xx + 磁盘缓存未过期 → 降级返回缓存。"""
    mock = MagicMock(status_code=500, text="")
    mocker.patch("pten.tools.ai_gateway.client.requests.post", return_value=mock)
    c = AIGatewayClient(keys=gw_keys)
    c._save_cache(BUNDLE)  # 预置有效磁盘缓存
    bundle = c.get_credentials()
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


def test_force_refresh_bypasses_memory(mocker, gw_keys):
    """force_refresh=True 即便内存缓存有效也向网关发请求。"""
    post = mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys)
    c.get_credentials()  # 第一次填充内存缓存
    assert post.call_count == 1
    c.get_credentials(force_refresh=True)  # 强制刷新，应再请求一次
    assert post.call_count == 2


def test_get_credentials_writes_disk_cache(mocker, gw_keys):
    """成功 fetch 后磁盘缓存文件确实写入且内容正确。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys)
    c.get_credentials()
    # 磁盘缓存文件已写入，且包含正确 bundle
    assert c.cache_path.is_file()
    cached = Keys.load_from_file(c.cache_path, c._cache_key)
    assert cached["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


def test_force_refresh_down_degrades_to_memory(mocker, gw_keys):
    """force_refresh=True + 网关不可达 + 内存有效 → 降级到内存缓存。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    c = AIGatewayClient(keys=gw_keys)
    c._memory_bundle = BUNDLE  # 预置内存缓存（无磁盘缓存）
    bundle = c.get_credentials(force_refresh=True)
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


def test_corrupted_cache_does_not_crash_degrade(mocker, gw_keys):
    """网关不可达 + 缓存文件损坏 → 抛 AIGatewayError，不抛 JSONDecodeError。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post",
        side_effect=requests.ConnectionError("down"),
    )
    c = AIGatewayClient(keys=gw_keys)
    # 写一个损坏的缓存文件
    c.cache_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(AIGatewayError):
        c.get_credentials()


def test_corrupted_cache_does_not_crash_save(mocker, gw_keys):
    """fetch 成功 + 旧缓存文件损坏 → 仍返回 bundle，save 不崩。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    c = AIGatewayClient(keys=gw_keys)
    c.cache_path.write_text("{not valid json", encoding="utf-8")
    bundle = c.get_credentials()
    assert bundle["api_key"] == "sk-real-xxxxxxxxxxxxwxyz"


# ---- AIGatewayLLM 便捷层 ----


def test_llm_get_completion(mocker, gw_keys):
    """AIGatewayLLM 用网关下发的 model 调用 OpenAI 兼容接口。"""
    mocker.patch(
        "pten.tools.ai_gateway.client.requests.post", return_value=_ok_response(BUNDLE)
    )
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="牛顿是物理学家"))]
    mock_openai = mocker.patch("pten.tools.ai_gateway.client.OpenAI")
    mock_openai.return_value.chat.completions.create.return_value = fake_resp

    llm = AIGatewayLLM(keys=gw_keys)
    assert llm.model == "deepseek-v4-flash"
    assert llm.get_completion("介绍牛顿") == "牛顿是物理学家"
    # 确认用网关下发的 model 调用
    args = mock_openai.return_value.chat.completions.create.call_args
    assert args.kwargs["model"] == "deepseek-v4-flash"
