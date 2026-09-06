import json
from unittest.mock import MagicMock

from pten.fs_bitable import FsBitable

from .conftest import assert_fs_response, create_fs_mock_response


def test_create_app(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {"code": 0, "msg": "success", "data": {"app": {"app_token": "appXXX"}}}
    )

    bitable = FsBitable(keys=fs_keys)
    response = bitable.create_app(name="一篇多维表格", folder_token="fldXXX")

    assert_fs_response(response)
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {"name": "一篇多维表格", "folder_token": "fldXXX"}
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer t-fake"
    assert headers["Content-Type"] == "application/json; charset=utf-8"


def test_create_table(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {"code": 0, "msg": "success", "data": {"table_id": "tblXXX"}}
    )

    bitable = FsBitable(keys=fs_keys)
    response = bitable.create_table(
        app_token="appXXX",
        name="数据表",
        fields=[{"field_name": "索引", "type": 1}],
    )

    assert_fs_response(response)
    # app_token 走路径参数，不在请求体里
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/tables"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {
        "table": {
            "name": "数据表",
            "fields": [{"field_name": "索引", "type": 1}],
        }
    }


def test_list_tables(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {
            "has_more": False,
            "total": 1,
            "items": [{"table_id": "tblXXX", "name": "数据表1", "revision": 1}],
        },
    }

    response = bitable.list_tables(app_token="appXXX", page_size=10)

    assert_fs_response(response)
    assert response["data"]["items"][0]["table_id"] == "tblXXX"
    # page_size 作为查询参数拼入 URL
    assert mock_get.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/tables?page_size=10"
    )
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_delete_table(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }

    response = bitable.delete_table(app_token="appXXX", table_id="tblXXX")

    assert_fs_response(response)
    assert mock_delete.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/tables/tblXXX"
    )
    # DELETE 无请求体
    assert "data" not in mock_delete.call_args.kwargs
    assert mock_delete.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_create_record(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {"code": 0, "msg": "success", "data": {"record": {"record_id": "recXXX"}}}
    )

    bitable = FsBitable(keys=fs_keys)
    response = bitable.create_record(
        app_token="appXXX",
        table_id="tblXXX",
        fields={"任务": "拜访客户", "工时": 10},
    )

    assert_fs_response(response)
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/tables/tblXXX/records"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {"fields": {"任务": "拜访客户", "工时": 10}}


def test_create_record_user_id_type(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    bitable = FsBitable(keys=fs_keys)
    bitable.create_record(
        app_token="appXXX",
        table_id="tblXXX",
        fields={"负责人": [{"id": "ou_x"}]},
        user_id_type="union_id",
    )
    # 传 user_id_type 时作为查询参数拼入 URL
    assert mock_post.call_args.args[0].endswith("records?user_id_type=union_id")

    # 不传时 URL 不带该查询参数（服务端默认 open_id）
    bitable.create_record(app_token="appXXX", table_id="tblXXX", fields={"负责人": []})
    assert "user_id_type" not in mock_post.call_args.args[0]


def test_delete_record(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    # 预置 token 缓存，避免触发 token 端点的真实请求
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"deleted": True, "record_id": "recXXX"},
    }

    response = bitable.delete_record(
        app_token="appXXX", table_id="tblXXX", record_id="recXXX"
    )

    assert_fs_response(response)
    assert mock_delete.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/"
        "tables/tblXXX/records/recXXX"
    )
    # DELETE 无请求体
    assert "data" not in mock_delete.call_args.kwargs
    assert mock_delete.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_delete_record_ignore_consistency(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {"code": 0, "msg": "success"}

    bitable.delete_record(
        app_token="appXXX",
        table_id="tblXXX",
        record_id="recXXX",
        ignore_consistency_check=True,
    )

    assert mock_delete.call_args.args[0].endswith(
        "records/recXXX?ignore_consistency_check=true"
    )


def test_bitable_token_refresh_on_expired(mocker, fs_keys):
    # 多维表格端点同样走 token 过期刷新重试
    responses = [
        MagicMock(json=lambda: {"code": 99991663, "msg": "invalid access token"}),
        MagicMock(
            json=lambda: {
                "code": 0,
                "msg": "ok",
                "tenant_access_token": "t-fresh",
                "expire": 7200,
            }
        ),
        MagicMock(json=lambda: {"code": 0, "msg": "success"}),
    ]
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = responses

    bitable = FsBitable(keys=fs_keys)
    # 预置一个未过期但已失效的 token，模拟"缓存的 token 被服务端判定过期"
    bitable.keys.save_access_token(bitable.api._token_key, "t-stale")

    response = bitable.create_app(name="x")

    assert_fs_response(response)
    assert mock_post.call_count == 3
    calls = mock_post.call_args_list
    assert calls[0].kwargs["headers"]["Authorization"] == "Bearer t-stale"
    # 刷新请求本身不携带 Authorization 头
    assert "Authorization" not in calls[1].kwargs["headers"]
    # 重试时换上了新 token
    assert calls[2].kwargs["headers"]["Authorization"] == "Bearer t-fresh"


def test_update_record(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_put = mocker.patch("requests.put")
    mock_put.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"record": {"record_id": "recXXX", "fields": {"名称": "updated"}}},
    }

    response = bitable.update_record(
        app_token="appXXX",
        table_id="tblXXX",
        record_id="recXXX",
        fields={"名称": "updated"},
    )

    assert_fs_response(response)
    assert response["data"]["record"]["record_id"] == "recXXX"
    assert mock_put.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/"
        "tables/tblXXX/records/recXXX"
    )
    body = json.loads(mock_put.call_args.kwargs["data"])
    assert body == {"fields": {"名称": "updated"}}
    assert mock_put.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_update_record_user_id_type(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_put = mocker.patch("requests.put")
    mock_put.return_value.json.return_value = {"code": 0, "msg": "success"}

    bitable.update_record(
        app_token="appXXX",
        table_id="tblXXX",
        record_id="recXXX",
        fields={"人员": [{"id": "ou_x"}]},
        user_id_type="union_id",
    )

    # user_id_type 作为查询参数拼入 URL
    assert mock_put.call_args.args[0].endswith("records/recXXX?user_id_type=union_id")
