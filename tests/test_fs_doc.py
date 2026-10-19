import json
from unittest.mock import MagicMock

import pytest

from pten.base_api import ApiException
from pten.fs_doc import FsDoc

from .conftest import assert_fs_response, create_fs_mock_response


def test_create_document(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {
            "code": 0,
            "msg": "success",
            "data": {
                "document": {
                    "document_id": "doxcnA",
                    "revision_id": 1,
                    "title": "新文档",
                }
            },
        }
    )

    doc = FsDoc(keys=fs_keys)
    response = doc.create_document(title="新文档", folder_token="fldXXX")

    assert_fs_response(response)
    assert response["data"]["document"]["document_id"] == "doxcnA"
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {"title": "新文档", "folder_token": "fldXXX"}
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer t-fake"
    assert headers["Content-Type"] == "application/json; charset=utf-8"


def test_create_document_no_args(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {"code": 0, "msg": "success", "data": {"document": {}}}
    )

    FsDoc(keys=fs_keys).create_document()

    # title/folder_token 均可选：不传时请求体为空 dict，不混入 null 字段
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {}


def test_get_document(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"document": {"document_id": "doxcnA", "revision_id": 2, "title": "t"}},
    }

    response = doc.get_document("doxcnA")

    assert_fs_response(response)
    assert response["data"]["document"]["revision_id"] == 2
    assert mock_get.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA"
    )
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_get_raw_content(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"content": "第一段\n第二段"},
    }

    response = doc.get_raw_content("doxcnA")

    assert_fs_response(response)
    assert response["data"]["content"] == "第一段\n第二段"
    assert mock_get.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA/raw_content"
    )
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def _mock_block_page(items, has_more=False, page_token=None):
    """构造 list_blocks 的 mock 响应（默认单页、无更多）。"""
    return {
        "code": 0,
        "msg": "success",
        "data": {"has_more": has_more, "page_token": page_token, "items": items},
    }


def _mock_file_page(files, has_more=False, next_page_token=None):
    """构造 list_folder_files 的 mock 响应（默认单页、无更多）。"""
    return {
        "code": 0,
        "msg": "success",
        "data": {
            "has_more": has_more,
            "next_page_token": next_page_token,
            "files": files,
        },
    }


def test_list_blocks_fetch_all(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 两页：第一页 has_more=True 带 page_token，第二页 has_more=False
    page1 = _mock_block_page(
        [{"block_id": "doxcnA", "block_type": 1, "children": ["b1"]}],
        has_more=True,
        page_token="tok2",
    )
    page2 = _mock_block_page([{"block_id": "b1", "block_type": 2}])
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = [
        MagicMock(json=lambda: page1),
        MagicMock(json=lambda: page2),
    ]

    # 不传 fetch_all（默认 True）：自动翻页聚合成响应 dict（data.items 为全部块）
    response = doc.list_blocks("doxcnA")

    assert [b["block_id"] for b in response["data"]["items"]] == ["doxcnA", "b1"]
    assert response["data"]["has_more"] is False
    assert response["data"]["total"] == 2
    assert mock_get.call_count == 2
    # page_size 缺省取 API 上限 500（最小化请求次数）；第二次请求带上第一页返回的 page_token
    assert "page_size=500" in mock_get.call_args_list[0].args[0]
    assert "page_token=tok2" in mock_get.call_args_list[1].args[0]


def test_list_blocks_single_page_returns_raw_response(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # fetch_all=False 返回原始响应 dict（含 has_more / page_token），翻页控制权在调用方
    raw = _mock_block_page([], has_more=True, page_token="tok2")
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = raw

    response = doc.list_blocks("doxcnA", fetch_all=False)

    assert response == raw
    # 单页模式不传 page_size（服务端默认 500）
    assert "page_size" not in mock_get.call_args.args[0]


def test_list_blocks_explicit_page_size_and_revision(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_block_page([])

    doc.list_blocks("doxcnA", page_size=100, document_revision_id=3)

    # fetch_all=True 时显式 page_size 优先，不被缺省 500 覆盖；
    # document_revision_id 作为查询参数拼入 URL
    url = mock_get.call_args.args[0]
    assert "page_size=100" in url
    assert "document_revision_id=3" in url


def test_list_folder_files_fetch_all(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 两页：第一页 has_more=True 带 next_page_token，第二页 has_more=False
    page1 = _mock_file_page(
        [{"token": "doxcnA", "type": "docx", "name": "文档A"}],
        has_more=True,
        next_page_token="tok2",
    )
    page2 = _mock_file_page([{"token": "fldcnB", "type": "folder", "name": "文件夹B"}])
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = [
        MagicMock(json=lambda: page1),
        MagicMock(json=lambda: page2),
    ]

    # 缺省 fetch_all=True：自动翻页聚合全部文件
    response = doc.list_folder_files("fldXXX")

    assert_fs_response(response)
    assert [f["token"] for f in response["data"]["files"]] == ["doxcnA", "fldcnB"]
    assert response["data"]["has_more"] is False
    assert response["data"]["total"] == 2
    assert mock_get.call_count == 2
    # page_size 缺省 200，与 folder_token 一起拼进查询串
    assert mock_get.call_args_list[0].args[0] == (
        "https://open.feishu.cn/open-apis/drive/v1/files?folder_token=fldXXX&page_size=200"
    )
    # 第二次请求带上第一页返回的 next_page_token
    assert "page_token=tok2" in mock_get.call_args_list[1].args[0]
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_list_folder_files_single_page_returns_raw_response(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # fetch_all=False：返回原始响应，翻页控制权在调用方
    raw = _mock_file_page([], has_more=True, next_page_token="tok2")
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = raw

    response = doc.list_folder_files("fldXXX", fetch_all=False, page_size=50)

    assert response == raw
    # 显式 page_size 原样透传（不被缺省 200 覆盖）
    assert "page_size=50" in mock_get.call_args.args[0]
    assert "page_size=200" not in mock_get.call_args.args[0]


def test_list_folder_files_root_no_pagination(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 根目录不拼 folder_token / 分页参数，仅发一次请求
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_file_page(
        [{"token": "doxcnA", "type": "docx", "name": "根目录文档"}]
    )

    response = doc.list_folder_files()

    assert_fs_response(response)
    assert response["data"]["total"] == 1
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args.args[0] == "https://open.feishu.cn/open-apis/drive/v1/files"
    )


def test_list_folder_files_order_and_user_id_type(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_file_page([])

    # 排序与 owner_id 的用户 ID 类型作为查询参数拼入 URL（对根目录同样生效）
    doc.list_folder_files(
        order_by="CreatedTime", direction="ASC", user_id_type="user_id"
    )

    url = mock_get.call_args.args[0]
    assert "order_by=CreatedTime" in url
    assert "direction=ASC" in url
    assert "user_id_type=user_id" in url


def test_append_text(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response(
        {
            "code": 0,
            "msg": "success",
            "data": {
                "children": [{"block_id": "doxcnB", "block_type": 2}],
                "document_revision_id": 2,
            },
        }
    )

    doc = FsDoc(keys=fs_keys)
    response = doc.append_text("doxcnA", "第一行\n第二行")

    assert_fs_response(response)
    # 文档根块的 block_id 即 document_id：URL 两处占位符都替换为 document_id
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA/blocks/doxcnA/children"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    # 多行文本进同一个文本块（\n 为软换行）；index 不传（服务端默认 -1 = 末尾）
    assert body == {
        "children": [
            {
                "block_type": 2,
                "text": {
                    "elements": [{"text_run": {"content": "第一行\n第二行"}}],
                    "style": {},
                },
            }
        ]
    }
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_append_text_blank(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")

    doc = FsDoc(keys=fs_keys)
    response = doc.append_text("doxcnA", "   \n  ")

    # 空白文本不发请求，返回错误 dict
    assert response == {"code": -1, "msg": "待插入的文本不能为空"}
    assert mock_post.call_count == 0


def _convert_blocks_response(first_level_ids, blocks):
    """构造 convert（markdown/HTML 转块）的 mock 响应。"""
    return {
        "code": 0,
        "msg": "success",
        "data": {"first_level_block_ids": first_level_ids, "blocks": blocks},
    }


def test_append_markdown(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # convert 产出临时 id 块树：heading + bullet（内嵌文本子块）
    convert_response = _convert_blocks_response(
        ["b1", "b2"],
        [
            {
                "block_id": "b1",
                "revision_id": 0,
                "parent_id": "",
                "block_type": 3,
                "heading1": {
                    "elements": [{"text_run": {"content": "标题"}}],
                    "style": {},
                },
                "children": [],
            },
            {
                "block_id": "b2",
                "revision_id": 0,
                "parent_id": "",
                "block_type": 12,
                "bullet": {
                    "elements": [{"text_run": {"content": "列表项"}}],
                    "style": {},
                },
                "children": ["b3"],
            },
            {
                "block_id": "b3",
                "revision_id": 0,
                "parent_id": "b2",
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": "子项"}}], "style": {}},
                "children": [],
            },
        ],
    )
    insert_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "block_id_relations": [
                {"block_id": "doxcnReal1", "temporary_block_id": "b1"}
            ],
            "document_revision_id": 3,
        },
    }
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: convert_response),
        MagicMock(json=lambda: insert_response),
    ]

    response = doc.append_markdown("doxcnA", "# 标题\n\n- 列表项\n  - 子项")

    assert response == insert_response
    calls = mock_post.call_args_list
    # 第一步 convert：全局端点，路径不含 document_id
    assert calls[0].args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/blocks/convert"
    )
    body1 = json.loads(calls[0].kwargs["data"])
    assert body1 == {
        "content_type": "markdown",
        "content": "# 标题\n\n- 列表项\n  - 子项",
    }
    # 第二步创建嵌套块：根块 block_id = document_id；children_id 即 first_level_block_ids，
    # descendants 按 BFS 文档顺序（b1、b2、b3）原样透传
    assert calls[1].args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA/blocks/doxcnA/descendant"
    )
    body2 = json.loads(calls[1].kwargs["data"])
    assert body2["children_id"] == ["b1", "b2"]
    assert [b["block_id"] for b in body2["descendants"]] == ["b1", "b2", "b3"]
    assert body2["descendants"][1]["children"] == ["b3"]
    assert "index" not in body2  # 缺省 -1 = 插入末尾
    assert calls[1].kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_append_markdown_strips_table_merge_info(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    table_block = {
        "block_id": "tbl1",
        "revision_id": 0,
        "parent_id": "",
        "block_type": 31,
        "table": {
            "property": {
                "row_size": 1,
                "column_size": 2,
                "merge_info": [{"row_span": 1, "col_span": 1}],
            }
        },
        "children": ["c1"],
    }
    cell_block = {
        "block_id": "c1",
        "revision_id": 0,
        "parent_id": "tbl1",
        "block_type": 32,
        "table_cell": {},
        "children": [],
    }
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(
            json=lambda: _convert_blocks_response(["tbl1"], [table_block, cell_block])
        ),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
    ]

    doc.append_markdown("doxcnA", "|a|b|\n|-|-|\n|1|2|")

    # merge_info 为只读字段，插入前被剥离；其余 property 原样保留
    body2 = json.loads(mock_post.call_args_list[1].kwargs["data"])
    table = body2["descendants"][0]
    assert "merge_info" not in table["table"]["property"]
    assert table["table"]["property"]["column_size"] == 2


def test_append_markdown_batches_over_limit(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 1001 个顶层单块子树：单次「创建嵌套块」上限 1000 块 → 两批（1000 + 1）
    first_level_ids = [f"t{i}" for i in range(1001)]
    blocks = [
        {
            "block_id": f"t{i}",
            "revision_id": 0,
            "parent_id": "",
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": f"行{i}"}}], "style": {}},
            "children": [],
        }
        for i in range(1001)
    ]
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: _convert_blocks_response(first_level_ids, blocks)),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
    ]
    # 拦截节流 sleep，测试不真实等待（第二批插入需等满最小编辑间隔）
    mock_sleep = mocker.patch("pten.fs_doc.time.sleep")

    doc.append_markdown("doxcnA", "x" * 5000)

    # convert + 两批插入，共 3 次请求；批量按顶层子树切分
    assert mock_post.call_count == 3
    body1 = json.loads(mock_post.call_args_list[1].kwargs["data"])
    body2 = json.loads(mock_post.call_args_list[2].kwargs["data"])
    assert len(body1["children_id"]) == 1000
    assert len(body1["descendants"]) == 1000
    assert len(body2["children_id"]) == 1
    assert len(body2["descendants"]) == 1
    # 第二批插入被编辑间隔节流（首批插入后不足间隔时长），避免背靠背连发撞限频
    mock_sleep.assert_called_once()


def test_append_markdown_single_subtree_over_limit(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 单个顶层子树自身超 1000 块（1 个 table + 1000 个子孙 = 1001 块，
    # 即超大表格的典型形状）：无法再按顶层子树切分，
    # convert 后直接 ValueError，绝不发起越界的整批插入
    child_ids = [f"c{i}" for i in range(1000)]
    big_tree = [
        {
            "block_id": "big1",
            "revision_id": 0,
            "parent_id": "",
            "block_type": 31,
            "table": {"property": {"row_size": 1000, "column_size": 1}},
            "children": child_ids,
        }
    ] + [
        {
            "block_id": cid,
            "revision_id": 0,
            "parent_id": "big1",
            "block_type": 32,
            "table_cell": {},
            "children": [],
        }
        for cid in child_ids
    ]
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: _convert_blocks_response(["big1"], big_tree)),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
    ]

    with pytest.raises(ValueError, match="子树"):
        doc.append_markdown("doxcnA", "|a|\n|-|\n|1|")

    # 只发了 convert（只读无副作用），未发起任何插入
    assert mock_post.call_count == 1


def test_append_markdown_blank(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")

    doc = FsDoc(keys=fs_keys)
    response = doc.append_markdown("doxcnA", "  \n ")

    # 空白 markdown 不发请求，返回错误 dict
    assert response == {"code": -1, "msg": "待插入的markdown不能为空"}
    assert mock_post.call_count == 0


def test_append_markdown_convert_error_aborts(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: {"code": 1770001, "msg": "convert failed"}),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
    ]

    # convert 失败（code != 0）直接抛 ApiException，绝不发起第二步插入
    with pytest.raises(ApiException) as exc_info:
        doc.append_markdown("doxcnA", "# t")
    assert exc_info.value.errCode == 1770001
    assert mock_post.call_count == 1


def test_delete_last_blocks(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 顶层块 [heading, bullet, bullet]（markdown 追加的典型形状）：
    # delete_last_blocks(count=2) 一次区间删除末尾两块，不限块类型
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_block_page(
        [
            {
                "block_id": "doxcnA",
                "block_type": 1,
                "children": ["doxcnH1", "doxcnB1", "doxcnB2"],
            },
            {"block_id": "doxcnH1", "block_type": 3, "heading1": {}},
            {"block_id": "doxcnB1", "block_type": 12, "bullet": {}},
            {"block_id": "doxcnB2", "block_type": 12, "bullet": {}},
        ]
    )
    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {"document_revision_id": 5},
    }

    response = doc.delete_last_blocks("doxcnA", count=2)

    assert_fs_response(response)
    # 父块是文档根块（block_id = document_id）；区间左闭右开 [len-count, len)
    assert mock_delete.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA/"
        "blocks/doxcnA/children/batch_delete"
    )
    body = json.loads(mock_delete.call_args.kwargs["data"])
    assert body == {"start_index": 1, "end_index": 3}
    assert mock_delete.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"
    # 快路径：根块在单页结果里即可定位，只发一次不带 page_size 的查询，不聚合
    assert mock_get.call_count == 1
    assert "page_size" not in mock_get.call_args.args[0]


def test_delete_last_blocks_default_count(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 缺省 count=1 删最后一块，任意类型（末尾是 heading 也照删，不限文本块）
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_block_page(
        [
            {"block_id": "doxcnA", "block_type": 1, "children": ["doxcnT1", "doxcnH1"]},
            {"block_id": "doxcnT1", "block_type": 2, "text": {}},
            {"block_id": "doxcnH1", "block_type": 3, "heading1": {}},
        ]
    )
    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }

    doc.delete_last_blocks("doxcnA")

    body = json.loads(mock_delete.call_args.kwargs["data"])
    assert body == {"start_index": 1, "end_index": 2}


def test_delete_last_blocks_clamp(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # count 超过顶层块数时按现有数量全删（clamp），不发越界区间
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_block_page(
        [
            {"block_id": "doxcnA", "block_type": 1, "children": ["doxcnB1", "doxcnB2"]},
            {"block_id": "doxcnB1", "block_type": 12, "bullet": {}},
            {"block_id": "doxcnB2", "block_type": 12, "bullet": {}},
        ]
    )
    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }

    doc.delete_last_blocks("doxcnA", count=10)

    body = json.loads(mock_delete.call_args.kwargs["data"])
    assert body == {"start_index": 0, "end_index": 2}


def test_delete_last_blocks_empty_document(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 空文档（根块无 children）→ 不删，返回 None
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = _mock_block_page(
        [{"block_id": "doxcnA", "block_type": 1, "children": []}]
    )
    mock_delete = mocker.patch("requests.delete")

    response = doc.delete_last_blocks("doxcnA")

    assert response is None
    assert mock_delete.call_count == 0


def test_delete_last_blocks_root_not_in_first_page(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 单页没拿到根块（根块理论上排在文档序第一位，此处模拟被排到后续页）→
    # 回退全量聚合翻页找到根块再删，正确性不依赖「根块必在首页」
    first_page = _mock_block_page(
        [{"block_id": "bX", "block_type": 2}], has_more=True, page_token="tok2"
    )
    root_page = _mock_block_page(
        [
            {"block_id": "doxcnA", "block_type": 1, "children": ["doxcnB1", "doxcnB2"]},
            {"block_id": "doxcnB1", "block_type": 12, "bullet": {}},
            {"block_id": "doxcnB2", "block_type": 12, "bullet": {}},
        ]
    )
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = [
        MagicMock(json=lambda: first_page),
        MagicMock(json=lambda: first_page),
        MagicMock(json=lambda: root_page),
    ]
    mock_delete = mocker.patch("requests.delete")
    mock_delete.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }

    response = doc.delete_last_blocks("doxcnA")

    assert_fs_response(response)
    assert mock_get.call_count == 3
    # 第一次单页查询不拼 page_size；回退聚合后按 500 上限翻页
    assert "page_size" not in mock_get.call_args_list[0].args[0]
    assert "page_size=500" in mock_get.call_args_list[1].args[0]
    assert "page_token=tok2" in mock_get.call_args_list[2].args[0]
    body = json.loads(mock_delete.call_args.kwargs["data"])
    assert body == {"start_index": 1, "end_index": 2}


def test_delete_last_blocks_invalid_count(fs_keys):
    doc = FsDoc(keys=fs_keys)

    # count < 1 是参数错误，直接 ValueError（不发任何请求）
    with pytest.raises(ValueError, match="count"):
        doc.delete_last_blocks("doxcnA", count=0)
    with pytest.raises(ValueError, match="count"):
        doc.delete_last_blocks("doxcnA", count=-1)


def test_append_markdown_from_file(mocker, fs_keys, tmp_path):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # Path 对象与 str 路径均可（open 两者都认）
    md_file = tmp_path / "notes.md"
    md_file.write_text("# 标题\n\n- 项目一\n", encoding="utf-8")

    insert_response = {"code": 0, "msg": "success", "data": {}}
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(
            json=lambda: _convert_blocks_response(
                ["b1"],
                [
                    {
                        "block_id": "b1",
                        "revision_id": 0,
                        "parent_id": "",
                        "block_type": 3,
                        "heading1": {
                            "elements": [{"text_run": {"content": "标题"}}],
                            "style": {},
                        },
                        "children": [],
                    }
                ],
            )
        ),
        MagicMock(json=lambda: insert_response),
    ]

    response = doc.append_markdown_from_file("doxcnA", md_file)

    assert response == insert_response
    # 文件内容原样进入 convert 请求体（两步流程与 append_markdown 完全一致）
    body = json.loads(mock_post.call_args_list[0].kwargs["data"])
    assert body == {"content_type": "markdown", "content": "# 标题\n\n- 项目一\n"}


def test_append_markdown_from_file_encoding(mocker, fs_keys, tmp_path):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # GBK 编码的旧文件：显式传 encoding 读取（缺省只认 utf-8）
    md_file = tmp_path / "notes_gbk.md"
    md_file.write_text("# 中文标题\n", encoding="gbk")

    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(
            json=lambda: _convert_blocks_response(
                ["b1"],
                [
                    {
                        "block_id": "b1",
                        "revision_id": 0,
                        "parent_id": "",
                        "block_type": 3,
                        "heading1": {
                            "elements": [{"text_run": {"content": "中文标题"}}],
                            "style": {},
                        },
                        "children": [],
                    }
                ],
            )
        ),
        MagicMock(json=lambda: {"code": 0, "msg": "success", "data": {}}),
    ]

    doc.append_markdown_from_file("doxcnA", str(md_file), encoding="gbk")

    body = json.loads(mock_post.call_args_list[0].kwargs["data"])
    assert body["content"] == "# 中文标题\n"


def test_append_markdown_from_file_blank(mocker, fs_keys, tmp_path):
    mock_post = mocker.patch("requests.post")

    md_file = tmp_path / "blank.md"
    md_file.write_text("  \n ", encoding="utf-8")

    doc = FsDoc(keys=fs_keys)
    response = doc.append_markdown_from_file("doxcnA", str(md_file))

    # 空白文件复用 append_markdown 的空白输入行为：不发请求，返回错误 dict
    assert response == {"code": -1, "msg": "待插入的markdown不能为空"}
    assert mock_post.call_count == 0


def _image_convert_response(image_url):
    """构造带图片占位块的 convert mock 响应（block_id_to_image_urls 给出临时块→图片源）。"""
    return {
        "code": 0,
        "msg": "success",
        "data": {
            "first_level_block_ids": ["b1", "b2"],
            "blocks": [
                {
                    "block_id": "b1",
                    "revision_id": 0,
                    "parent_id": "",
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": "正文"}}],
                        "style": {},
                    },
                    "children": [],
                },
                {
                    "block_id": "b2",
                    "revision_id": 0,
                    "parent_id": "",
                    "block_type": 27,
                    "image": {"width": 240, "height": 240, "token": ""},
                    "children": [],
                },
            ],
            "block_id_to_image_urls": [{"block_id": "b2", "image_url": image_url}],
        },
    }


def test_append_markdown_with_image(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    image_url = "https://cdn.example.com/img/logo.png?v=2"
    insert_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "block_id_relations": [
                {"block_id": "doxcnReal1", "temporary_block_id": "b1"},
                {"block_id": "doxcnReal2", "temporary_block_id": "b2"},
            ],
            "document_revision_id": 4,
        },
    }
    upload_response = {
        "code": 0,
        "msg": "success",
        "data": {"file_token": "boxcnFake1"},
    }
    # 图片下载走 requests.get（与 convert/insert/upload 的 POST 互不干扰）
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.content = b"PNGDATA"
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: _image_convert_response(image_url)),
        MagicMock(json=lambda: insert_response),
        MagicMock(json=lambda: upload_response),
    ]
    mock_patch = mocker.patch("requests.patch")
    mock_patch.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }
    # 拦截节流 sleep，测试不真实等待（插入后紧接着 replace_image 回写需等编辑间隔）
    mocker.patch("pten.fs_doc.time.sleep")

    response = doc.append_markdown("doxcnA", f"# t\n\n![logo]({image_url})\n\n正文")

    assert response == insert_response
    assert mock_get.call_args.args[0] == image_url
    # 外链图片下载带超时，避免单个挂起的图片源阻塞整次追加
    assert mock_get.call_args.kwargs["timeout"] == FsDoc._IMAGE_DOWNLOAD_TIMEOUT
    # 下载外链图片带浏览器风格 UA：部分 CDN 拒绝 python-requests 默认 UA（403）
    assert "User-Agent" in mock_get.call_args.kwargs["headers"]
    # 上传图片素材：纯 multipart 表单（无 JSON body、URL 无查询参数）
    upload_call = mock_post.call_args_list[2]
    assert upload_call.args[0] == (
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    )
    files = upload_call.kwargs["files"]
    assert files["parent_type"] == (None, "docx_image")
    assert files["parent_node"] == (None, "doxcnReal2")
    # 文件名取 URL 路径末段（剥离查询串）
    assert files["file_name"] == (None, "logo.png")
    assert files["size"] == (None, str(len(b"PNGDATA")))
    assert files["file"] == ("logo.png", b"PNGDATA")
    assert "data" not in upload_call.kwargs
    headers = upload_call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer t-fake"
    # multipart 的 boundary 由 requests 生成，不能手动带 Content-Type
    assert "Content-Type" not in headers
    # replace_image 回写：PATCH 到真实图片块；不传宽高，服务端自动探测实际尺寸
    assert mock_patch.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/docx/v1/documents/doxcnA/blocks/doxcnReal2"
    )
    body = json.loads(mock_patch.call_args.kwargs["data"])
    assert body == {"replace_image": {"token": "boxcnFake1"}}
    assert mock_patch.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_append_markdown_image_url_percent_decoded(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # URL 编码的中文文件名（%E5%9B%BE.png 即 图.png）：上传的 file_name 做 percent
    # 解码，不把 %xx 字面量带进飞书
    image_url = "https://cdn.example.com/img/%E5%9B%BE.png?v=2"
    insert_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "block_id_relations": [
                {"block_id": "doxcnReal2", "temporary_block_id": "b2"}
            ]
        },
    }
    upload_response = {
        "code": 0,
        "msg": "success",
        "data": {"file_token": "boxcnFake1"},
    }
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.content = b"PNGDATA"
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: _image_convert_response(image_url)),
        MagicMock(json=lambda: insert_response),
        MagicMock(json=lambda: upload_response),
    ]
    mock_patch = mocker.patch("requests.patch")
    mock_patch.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }
    # 拦截节流 sleep，测试不真实等待（插入后紧接着 replace_image 回写需等编辑间隔）
    mocker.patch("pten.fs_doc.time.sleep")

    doc.append_markdown("doxcnA", f"![图]({image_url})")

    files = mock_post.call_args_list[2].kwargs["files"]
    assert files["file_name"] == (None, "图.png")
    assert files["file"] == ("图.png", b"PNGDATA")


def test_append_markdown_from_file_local_image(mocker, fs_keys, tmp_path):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # md 与图片同目录：相对路径图片按 md 文件所在目录解析，不发起网络下载
    (tmp_path / "pic.png").write_bytes(b"LOCALPNG")
    md_file = tmp_path / "report.md"
    md_file.write_text("![本地图](pic.png)\n", encoding="utf-8")

    insert_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "block_id_relations": [{"block_id": "doxcnImg", "temporary_block_id": "b2"}]
        },
    }
    upload_response = {
        "code": 0,
        "msg": "success",
        "data": {"file_token": "boxcnLocal"},
    }
    mock_get = mocker.patch("requests.get")
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(json=lambda: _image_convert_response("pic.png")),
        MagicMock(json=lambda: insert_response),
        MagicMock(json=lambda: upload_response),
    ]
    mock_patch = mocker.patch("requests.patch")
    mock_patch.return_value.json.return_value = {
        "code": 0,
        "msg": "success",
        "data": {},
    }
    # 拦截节流 sleep，测试不真实等待（插入后紧接着 replace_image 回写需等编辑间隔）
    mocker.patch("pten.fs_doc.time.sleep")

    response = doc.append_markdown_from_file("doxcnA", md_file)

    assert response == insert_response
    assert mock_get.call_count == 0
    files = mock_post.call_args_list[2].kwargs["files"]
    assert files["file_name"] == (None, "pic.png")
    assert files["size"] == (None, str(len(b"LOCALPNG")))
    assert files["file"] == ("pic.png", b"LOCALPNG")
    assert files["parent_node"] == (None, "doxcnImg")
    body = json.loads(mock_patch.call_args.kwargs["data"])
    assert body == {"replace_image": {"token": "boxcnLocal"}}


def test_append_markdown_image_failure_tolerated(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    doc.keys.save_access_token(doc.api._token_key, "t-fake")

    # 图片下载失败：块照常插入、返回插入响应，仅不回填素材（占位块保留）
    insert_response = {
        "code": 0,
        "msg": "success",
        "data": {
            "block_id_relations": [
                {"block_id": "doxcnReal2", "temporary_block_id": "b2"}
            ]
        },
    }
    mock_get = mocker.patch("requests.get")
    mock_get.side_effect = Exception("download failed")
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [
        MagicMock(
            json=lambda: _image_convert_response("https://cdn.example.com/x.png")
        ),
        MagicMock(json=lambda: insert_response),
    ]
    mock_patch = mocker.patch("requests.patch")

    response = doc.append_markdown("doxcnA", "![x](https://cdn.example.com/x.png)")

    assert response == insert_response
    assert mock_post.call_count == 2  # convert + insert（下载失败，未到上传）
    assert mock_patch.call_count == 0


def test_pace_docx_edit_throttles_edit_requests(mocker, fs_keys):
    doc = FsDoc(keys=fs_keys)
    mock_sleep = mocker.patch("pten.fs_doc.time.sleep")

    # 首个编辑类请求不等待（_last_edit_time 初始为 0）
    doc._pace_docx_edit()
    mock_sleep.assert_not_called()

    # 紧随其后的第二个编辑类请求需等满最小间隔（官方限频：每秒 3 次编辑）
    doc._pace_docx_edit()
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args.args[0] == pytest.approx(
        FsDoc._DOCX_EDIT_INTERVAL, abs=0.05
    )
