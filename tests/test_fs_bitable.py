import json
from unittest.mock import MagicMock

import pytest

from pten.fs_bitable import FsBitable, FsFieldType

from .conftest import assert_fs_response, create_fs_mock_response


def _mock_field_list(items, has_more=False, page_token=None):
    """构造 list_fields 的 mock 响应（默认单页、无更多）。"""
    return {
        "code": 0,
        "msg": "success",
        "data": {"has_more": has_more, "page_token": page_token, "items": items},
    }


def test_readonly_types_membership():
    """READONLY_TYPES 须精确覆盖全部只读字段类型。

    新增只读类型时必须同步加入本集合，否则 validate_record_fields 会放行该类型、
    预检失效。本测试钉死集合成员，使任何增删成为有意识的测试改动。
    """
    assert FsFieldType.READONLY_TYPES == frozenset(
        {
            FsFieldType.LOOKUP,
            FsFieldType.FORMULA,
            FsFieldType.WORKFLOW,
            FsFieldType.CREATED_TIME,
            FsFieldType.MODIFIED_TIME,
            FsFieldType.CREATED_USER,
            FsFieldType.MODIFIED_USER,
            FsFieldType.AUTO_NUMBER,
            FsFieldType.BUTTON,
        }
    )


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


def test_create_table_with_field_type_enum(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {"code": 0, "msg": "success", "data": {"table_id": "tblXXX"}}
    )

    bitable = FsBitable(keys=fs_keys)
    response = bitable.create_table(
        app_token="appXXX",
        name="数据表",
        fields=[
            {"field_name": "姓名", "type": FsFieldType.TEXT},
            {
                "field_name": "生日",
                "type": FsFieldType.DATETIME,
                "property": {"date_formatter": "yyyy/MM/dd"},
            },
        ],
    )

    assert_fs_response(response)
    # IntEnum 经 json 序列化后仍是数字，与裸数字写法完全等价
    assert FsFieldType.TEXT == 1
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {
        "table": {
            "name": "数据表",
            "fields": [
                {"field_name": "姓名", "type": 1},
                {
                    "field_name": "生日",
                    "type": 5,
                    "property": {"date_formatter": "yyyy/MM/dd"},
                },
            ],
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


def test_list_fields(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_field_list(
        [
            {"field_id": "fld1", "field_name": "姓名", "type": 1, "ui_type": "Text"},
            {"field_id": "fld2", "field_name": "年龄", "type": 2, "ui_type": "Number"},
        ]
    )

    response = bitable.list_fields(app_token="appXXX", table_id="tblXXX", page_size=10)

    assert_fs_response(response)
    assert response["data"]["items"][0]["field_id"] == "fld1"
    # app_token / table_id 走路径参数，page_size 作为查询参数拼入 URL
    assert mock_get.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/bitable/v1/apps/appXXX/"
        "tables/tblXXX/fields?page_size=10"
    )
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_list_fields_view_id(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_field_list([])

    bitable.list_fields(app_token="appXXX", table_id="tblXXX", view_id="vewXXX")

    # view_id 作为查询参数拼入 URL
    assert "view_id=vewXXX" in mock_get.call_args.args[0]


def test_list_fields_text_field_as_array(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_field_list([])

    bitable.list_fields(app_token="appXXX", table_id="tblXXX", text_field_as_array=True)

    # 布尔须小写 true，不能是 Python 的 True
    assert "text_field_as_array=true" in mock_get.call_args.args[0]
    assert "True" not in mock_get.call_args.args[0]


def test_validate_record_fields_unknown(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_field_list(
        [{"field_id": "fld1", "field_name": "姓名", "type": 1}]
    )

    # raise_on_error=False：返回问题列表，不抛错；未知字段被检出，已知字段不报
    issues = bitable.validate_record_fields(
        app_token="appXXX",
        table_id="tblXXX",
        fields={"姓名": "张三", "不存在的字段": "x"},
        raise_on_error=False,
    )
    assert any("不存在的字段" in i for i in issues)
    assert not any("姓名" in i for i in issues)

    # raise_on_error=True（默认）：校验不过抛 ValueError，信息含未知字段提示
    with pytest.raises(ValueError, match="不存在"):
        bitable.validate_record_fields(
            app_token="appXXX", table_id="tblXXX", fields={"不存在": "x"}
        )


def test_validate_record_fields_readonly(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    # 公式字段 type=20，只读；文本字段 type=1，可写
    mock_get.return_value.json.return_value = _mock_field_list(
        [
            {"field_id": "fld1", "field_name": "姓名", "type": 1},
            {"field_id": "fld2", "field_name": "计算结果", "type": FsFieldType.FORMULA},
        ]
    )

    issues = bitable.validate_record_fields(
        app_token="appXXX",
        table_id="tblXXX",
        fields={"姓名": "张三", "计算结果": 123},
        raise_on_error=False,
    )
    # 公式字段被识别为只读，可写字段不报
    assert any("计算结果" in i and "只读" in i for i in issues)
    assert not any("姓名" in i for i in issues)


def test_validate_record_fields_ok(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_field_list(
        [
            {"field_id": "fld1", "field_name": "姓名", "type": 1},
            {"field_id": "fld2", "field_name": "年龄", "type": 2},
        ]
    )

    # 全部为合法可写字段，返回空列表（默认 raise_on_error=True 也不抛错）
    issues = bitable.validate_record_fields(
        app_token="appXXX",
        table_id="tblXXX",
        fields={"姓名": "张三", "年龄": 18},
    )
    assert issues == []


def test_validate_record_fields_paginated(mocker, fs_keys):
    bitable = FsBitable(keys=fs_keys)
    bitable.keys.save_access_token(bitable.api._token_key, "t-fake")

    # 两页：第一页 has_more=True 带 page_token，第二页 has_more=False
    page1 = _mock_field_list(
        [{"field_id": "fld1", "field_name": "字段A", "type": 1}],
        has_more=True,
        page_token="tok2",
    )
    page2 = _mock_field_list(
        [{"field_id": "fld2", "field_name": "字段B", "type": 2}],
        has_more=False,
    )
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = [
        MagicMock(json=lambda: page1),
        MagicMock(json=lambda: page2),
    ]

    issues = bitable.validate_record_fields(
        app_token="appXXX",
        table_id="tblXXX",
        # 字段A、字段B 分属两页（合法），字段C 不在两页里（未知）
        fields={"字段A": "x", "字段B": 1, "字段C": "y"},
        raise_on_error=False,
    )
    # 两页字段都被聚合：A、B 合法，C 未知
    assert any("字段C" in i for i in issues)
    assert not any("字段A" in i or "字段B" in i for i in issues)
    assert mock_get.call_count == 2
    # 第二次请求带上了第一页返回的 page_token
    assert "page_token=tok2" in mock_get.call_args_list[1].args[0]
