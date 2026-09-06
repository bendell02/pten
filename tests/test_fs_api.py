import json
from unittest.mock import MagicMock

import pytest

from pten.base_api import ApiException
from pten.fs_api import BOT_API_TYPE, CORP_API_TYPE, FsBotApi, FsCorpApi
from pten.keys import Keys

from .conftest import assert_fs_response, create_fs_mock_response


def test_bot_api(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"code": 0, "msg": "success"}

    api = FsBotApi("pten_keys_example.ini")
    response = api.http_call(
        BOT_API_TYPE["WEBHOOK_SEND"],
        {"msg_type": "text", "content": {"text": "hello from bot"}},
    )

    assert_fs_response(response)
    # webhook key 从 [fs] 配置拼进 URL，请求不携带鉴权头
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bot/v2/hook/cb46342e-4ecb-436c-b91d-6abcabc8c033e"
    )
    assert "Authorization" not in mock_post.call_args.kwargs["headers"]


def test_refresh_tenant_access_token(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {
        "code": 0,
        "msg": "ok",
        "tenant_access_token": "t-fake",
        "expire": 7200,
    }

    api = FsCorpApi(keys=fs_keys)
    assert api.refresh_access_token() == "t-fake"

    # 请求发往获取 tenant_access_token 的端点，请求体携带 [fs] 的凭证
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/"
        + CORP_API_TYPE["GET_TENANT_ACCESS_TOKEN"][0]
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {"app_id": "cli_slkdjalasdkjasd", "app_secret": "dskLLdkasdjlasdKK"}
    # 获取 token 的端点本身不携带 Authorization 头
    assert "Authorization" not in mock_post.call_args.kwargs["headers"]
    # token 已写入 Keys 的缓存，可直接读回
    assert fs_keys.get_access_token(api._token_key) == "t-fake"


def test_tenant_api_custom_credentials(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {
        "code": 0,
        "msg": "ok",
        "tenant_access_token": "t-custom",
        "expire": 7200,
    }

    # 显式传入的凭证优先于配置文件
    api = FsCorpApi(app_id="cli_custom", app_secret="secret_custom", keys=fs_keys)
    assert api.refresh_access_token() == "t-custom"

    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {"app_id": "cli_custom", "app_secret": "secret_custom"}


def test_get_tenant_access_token_cached(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    api = FsCorpApi(keys=fs_keys)
    assert api.get_access_token() == "t-fake"
    assert api.get_access_token() == "t-fake"
    # 第二次命中内存缓存，不再发起 HTTP 请求
    assert mock_post.call_count == 1


def test_get_tenant_access_token_refresh_when_expired(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    api = FsCorpApi(keys=fs_keys)
    # 预置一个已过期的 token 文件，应触发刷新
    Keys.save_to_file(
        fs_keys.TOKEN_PATH,
        api._token_key,
        {"access_token": "t-stale", "expire_time": 1},
    )

    assert api.get_access_token() == "t-fake"


def test_tenant_api_authorization_header(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    api = FsCorpApi(keys=fs_keys)
    response = api.http_call(
        ["im/v1/messages?receive_id_type=open_id", "POST"], {"test": "data"}
    )

    assert_fs_response(response)
    headers = mock_post.call_args.kwargs["headers"]
    # 普通端点通过 Authorization 头携带 tenant_access_token
    assert headers["Authorization"] == "Bearer t-fake"
    assert headers["Content-Type"] == "application/json; charset=utf-8"


def test_tenant_api_retry_on_expired_token(mocker, fs_keys):
    responses = [
        # 携带旧 token 的请求：token 已失效
        MagicMock(json=lambda: {"code": 99991663, "msg": "invalid access token"}),
        # 刷新 token
        MagicMock(
            json=lambda: {
                "code": 0,
                "msg": "ok",
                "tenant_access_token": "t-fresh",
                "expire": 7200,
            }
        ),
        # 携带新 token 重试成功
        MagicMock(json=lambda: {"code": 0, "msg": "success"}),
    ]
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = responses

    api = FsCorpApi(keys=fs_keys)
    # 预置一个未过期但已失效的 token，模拟"缓存的 token 被服务端判定过期"
    fs_keys.save_access_token(api._token_key, "t-stale")

    response = api.http_call(
        ["im/v1/messages?receive_id_type=open_id", "POST"], {"test": "data"}
    )

    assert_fs_response(response)
    assert mock_post.call_count == 3
    calls = mock_post.call_args_list
    assert calls[0].kwargs["headers"]["Authorization"] == "Bearer t-stale"
    # 刷新请求本身不携带 Authorization 头
    assert "Authorization" not in calls[1].kwargs["headers"]
    # 重试时换上了新 token
    assert calls[2].kwargs["headers"]["Authorization"] == "Bearer t-fresh"


def test_tenant_api_error_response(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"code": 10003, "msg": "app not found"}

    api = FsCorpApi(keys=fs_keys)
    with pytest.raises(ApiException) as exc_info:
        api.refresh_access_token()
    assert exc_info.value.errCode == 10003
    assert exc_info.value.errMsg == "app not found"
