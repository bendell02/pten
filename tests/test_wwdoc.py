from pten.wwdoc import Doc

from .conftest import assert_ww_response


def test_wedoc(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "errcode": 0,
        "errmsg": "ok",
        "access_token": "fake_token",
    }

    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}

    wwdoc = Doc("pten_keys_example.ini")

    doc_type = 10
    doc_name = "test_smart_table2"
    admin_users = ["a", "b"]
    response = wwdoc.create_doc(doc_type, doc_name, admin_users=admin_users)
    assert_ww_response(response)

    docid = "your_docid"

    new_name = "new_name"
    response = wwdoc.rename_doc(new_name, docid=docid)
    assert_ww_response(response)

    response = wwdoc.get_doc_base_info(docid)
    assert_ww_response(response)

    response = wwdoc.get_doc_share_url(docid=docid)
    assert_ww_response(response)

    requests = {"insert_text": {"text": "text content", "location": {"index": 0}}}
    response = wwdoc.udpate_doc(docid, requests)
    assert_ww_response(response)

    properties = {"title": "智能表", "index": 3}
    response = wwdoc.smartsheet_add_sheet(docid, properties)
    assert_ww_response(response)

    sheet_id = "bG1daQ"

    response = wwdoc.smartsheet_delete_sheet(docid, sheet_id)
    assert_ww_response(response)

    title = "new title"
    response = wwdoc.smartsheet_update_sheet(docid, sheet_id, title)
    assert_ww_response(response)

    view_title = "view_title"
    view_type = "VIEW_TYPE_GRID"
    response = wwdoc.smartsheet_add_view(docid, sheet_id, view_title, view_type)
    assert_ww_response(response)

    view_ids = ["vZlli6"]
    response = wwdoc.smartsheet_delete_view(docid, sheet_id, view_ids)
    assert_ww_response(response)

    sheet_id = "N0OBq1"
    view_id = "v7w2JH"
    view_title = "view_title2"
    response = wwdoc.smartsheet_update_view(docid, sheet_id, view_id, view_title)
    assert_ww_response(response)

    fields = [{"field_title": "TITLE", "field_type": "FIELD_TYPE_TEXT"}]
    response = wwdoc.smartsheet_add_fields(docid, sheet_id, fields)
    assert_ww_response(response)
    fields = [
        {
            "field_title": "number",
            "field_type": "FIELD_TYPE_NUMBER",
            "property_number": {"decimal_places": 2, "use_separate": False},
        }
    ]
    response = wwdoc.smartsheet_add_fields(docid, sheet_id, fields)
    assert_ww_response(response)

    field_ids = ["fBOiQ6"]
    response = wwdoc.smartsheet_delete_fields(docid, sheet_id, field_ids)
    assert_ww_response(response)

    update_fileds = [
        {
            "field_id": "fVKMWE",
            "field_title": "number2",
            "field_type": "FIELD_TYPE_NUMBER",
            "property_number": {"decimal_places": 0, "use_separate": False},
        }
    ]
    response = wwdoc.smartsheet_update_fields(docid, sheet_id, update_fileds)
    assert_ww_response(response)

    records = [
        {
            "values": {
                "智能表列": [{"type": "text", "text": "文本内容2byAPP  3"}],
                "number2": 36,
            }
        }
    ]
    key_type = "CELL_VALUE_KEY_TYPE_FIELD_TITLE"
    response = wwdoc.smartsheet_add_records(docid, sheet_id, records, key_type)
    assert_ww_response(response)

    record_ids = ["rBtA4S", "rQnDtO"]
    response = wwdoc.smartsheet_delete_records(docid, sheet_id, record_ids)
    assert_ww_response(response)

    record_id = "rKbfgH"
    update_records = [
        {
            "record_id": record_id,
            "values": {
                "智能表列": [{"type": "text", "text": "文本内容2byAPP5"}],
                "number2": 37,
            },
        }
    ]
    response = wwdoc.smartsheet_update_records(docid, sheet_id, update_records)
    assert_ww_response(response)

    response = wwdoc.smartsheet_get_sheet(docid)
    assert_ww_response(response)

    response = wwdoc.smartsheet_get_views(docid, sheet_id)
    assert_ww_response(response)

    response = wwdoc.smartsheet_get_fields(docid, sheet_id)
    assert_ww_response(response)

    response = wwdoc.smartsheet_get_records(docid, sheet_id)
    assert_ww_response(response)

    type = 1
    response = wwdoc.smartsheet_get_sheet_priv(docid, type)
    assert_ww_response(response)

    response = wwdoc.get_doc_auth(docid)
    assert_ww_response(response)

    doc_join_rule = {
        "enable_corp_internal": True,
        "corp_internal_auth": 2,
        "enable_corp_external": True,
        "corp_external_auth": 1,
        "corp_internal_approve_only_by_admin": False,
        "corp_external_approve_only_by_admin": False,
        "ban_share_external": False,
    }
    response = wwdoc.mod_doc_join_rule(docid, **doc_join_rule)
    assert_ww_response(response)

    member_list_rule = {
        "update_file_member_list": [{"type": 1, "auth": 7, "userid": "USERID1"}],
        "del_file_member_list": [
            {"type": 1, "userid": "USERID2"},
            {"type": 1, "tmp_external_userid": "TMP_EXTERNAL_USERID2"},
        ],
    }
    response = wwdoc.mod_doc_join_rule(docid, **member_list_rule)
    assert_ww_response(response)

    safety_setting = {
        "enable_readonly_copy": False,
        "watermark": {
            "margin_type": 2,
            "show_visitor_name": True,
            "show_text": True,
            "text": "test mark",
        },
    }
    response = wwdoc.mod_doc_safety_setting(docid, **safety_setting)
    assert_ww_response(response)

    form_info = {
        "form_title": "FORM_TITLE",
        "form_desc": "FORM_DESC",
        "form_question": {
            "items": [
                {
                    "question_id": 1,
                    "title": "are you OK?",
                    "pos": 1,
                    "status": 1,
                    "reply_type": 1,
                    "must_reply": True,
                    "note": "NOTE",
                    "option_item": [{"key": 1, "value": "VALUE", "status": 1}],
                    "placeholder": "PLACEHOLDER",
                    "question_extend_setting": {},
                }
            ]
        },
    }
    response = wwdoc.create_form(form_info)
    assert_ww_response(response)

    form_id = "your_form_id"
    response = wwdoc.get_form_info(form_id)
    assert_ww_response(response)
