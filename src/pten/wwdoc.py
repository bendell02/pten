"""
pten.wwdoc
~~~~~~~~~~~~

This module implements the Doc class.

"""

from .keys import Keys
from .wwapi import CORP_API_TYPE, CorpApi


class Doc:
    """
    应用在调用文档接口前，需要先获得文档的使用权限：
    自建应用: 登录企业微信管理端，进入「协作」-「文档」-「API」,配置「可调用接口的应用」
    第三方应用: 第三方服务商创建应用的时候，需要开启“文档接口权限”，企业授权安装第三方应用之后，第三方应用即拥有了调用文档接口的权限
    代开发自建应用: 第三方服务商为企业配置代开发应用时，需要开启「文档接口权限」，企业管理员确认之后，应用即拥有文档权限
    """

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
        self.keys = keys if keys else Keys(keys_filepath)
        self.api = CorpApi(keys_filepath, keys=keys)

    def create_doc(self, doc_type, doc_name, **kwargs):
        data = {"doc_type": doc_type, "doc_name": doc_name}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["WEDOC_CREATE"], data)

    def solve_docid_formid(self, docid, formid):
        if docid and formid:
            raise ValueError("docid and formid cannot be provided at the same time")

        if docid is None and formid is None:
            raise ValueError("docid or formid must be provided")

        data = {}
        if docid is not None:
            data["docid"] = docid
        else:
            data["formid"] = formid

        return data

    def rename_doc(self, new_name, docid=None, formid=None):
        data = self.solve_docid_formid(docid, formid)
        data = {"new_name": new_name}

        return self.api.http_call(CORP_API_TYPE["WEDOC_RENAME"], data)

    def delete_doc(self, docid, formid=None):
        """
        仅可删除应用自己创建的文档和收集表
        """
        data = self.solve_docid_formid(docid, formid)
        return self.api.http_call(CORP_API_TYPE["WEDOC_DELETE"], data)

    def get_doc_base_info(self, docid):
        data = {"docid": docid}
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_BASIC_INFO"], data)

    def get_doc_share_url(self, docid=None, formid=None):
        data = self.solve_docid_formid(docid, formid)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SHARE"], data)

    def udpate_doc(self, docid, requests, version=None):
        """
        https://developer.work.weixin.qq.com/document/path/97626  里有多种编辑文档的操作
        """
        data = {"docid": docid, "requests": requests, "version": version}
        if version:
            data["version"] = version

        return self.api.http_call(CORP_API_TYPE["WEDOC_BATCH_UPDATE"], data)

    def update_spreadsheet(self, docid, requests):
        """
        https://developer.work.weixin.qq.com/document/path/97628  里有多种编辑文档的操作
        """
        data = {"docid": docid, "requests": requests}
        return self.api.http_call(CORP_API_TYPE["WEDOC_SPREADSHEET_BATCH_UPDATE"], data)

    def get_doc(self, docid):
        """
        用于获取文档数据  https://developer.work.weixin.qq.com/document/path/97659
        """
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_DOC"], {"docid": docid})

    def get_spreadsheet_properties(self, docid):
        return self.api.http_call(
            CORP_API_TYPE["WEDOC_SPREADSHEET_GET_PROPERTITIES"], {"docid": docid}
        )

    def get_spreadsheet_range_data(self, docid, sheetid, range):
        return self.api.http_call(
            CORP_API_TYPE["WEDOC_SPREADSHEET_GET_RANGE_DATA"],
            {"docid": docid, "sheet_id": sheetid, "range": range},
        )

    def smartsheet_add_sheet(self, docid, properties):
        data = {"docid": docid, "properties": properties}
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_ADD_SHEET"], data)

    def smartsheet_delete_sheet(self, docid, sheet_id):
        data = {"docid": docid, "sheet_id": sheet_id}
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_DELETE_SHEET"], data)

    def smartsheet_update_sheet(self, docid, sheet_id, title):
        """
        用于修改表格中某个子表的标题。
        """
        data = {"docid": docid, "properties": {"sheet_id": sheet_id, "title": title}}
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_UPDATE_SHEET"], data)

    def smartsheet_add_view(self, docid, sheet_id, view_title, view_type, **kwargs):
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "view_title": view_title,
            "view_type": view_type,
        }
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_ADD_VIEW"], data)

    def smartsheet_delete_view(self, docid, sheet_id, view_ids):
        data = {"docid": docid, "sheet_id": sheet_id, "view_ids": view_ids}
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_DELETE_VIEW"], data)

    def smartsheet_update_view(
        self, docid, sheet_id, view_id, view_title=None, **kwargs
    ):
        """
        https://developer.work.weixin.qq.com/document/path/100219 可查看property
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "view_id": view_id,
        }
        if view_title:
            data["view_title"] = view_title
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_UPDATE_VIEW"], data)

    def smartsheet_add_fields(self, docid, sheet_id, fields):
        """
        https://developer.work.weixin.qq.com/document/path/100220
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "fields": fields,
        }
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_ADD_FIELDS"], data)

    def smartsheet_delete_fields(self, docid, sheet_id, field_ids):
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "field_ids": field_ids,
        }
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_DELETE_FIELDS"], data)

    def smartsheet_update_fields(self, docid, sheet_id, fields):
        """
        https://developer.work.weixin.qq.com/document/path/100222
        该接口只能更新字段名、字段属性，不能更新字段类型。
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "fields": fields,
        }
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_UPDATE_FIELDS"], data)

    def smartsheet_add_records(self, docid, sheet_id, records, key_type=None):
        """
        https://developer.work.weixin.qq.com/document/path/100224
        records里values的 key 为字段标题或字段 ID, 由key_type决定
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "key_type": "CELL_VALUE_KEY_TYPE_FIELD_TITLE",
            "records": records,
        }
        if key_type:
            data["key_type"] = key_type
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_ADD_RECORDS"], data)

    def smartsheet_delete_records(self, docid, sheet_id, record_ids):
        return self.api.http_call(
            CORP_API_TYPE["WEDOC_SMARTSHEET_DELETE_RECORDS"],
            {"docid": docid, "sheet_id": sheet_id, "record_ids": record_ids},
        )

    def smartsheet_update_records(self, docid, sheet_id, update_records, key_type=None):
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "records": update_records,
        }
        if key_type:
            data["key_type"] = key_type

        return self.api.http_call(
            CORP_API_TYPE["WEDOC_SMARTSHEET_UPDATE_RECORDS"], data
        )

    def smartsheet_get_sheet(self, docid, sheet_id=None, need_all_type_sheet=True):
        data = {"docid": docid}
        if sheet_id:
            data["sheet_id"] = sheet_id
        if need_all_type_sheet:
            data["need_all_type_sheet"] = need_all_type_sheet

        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_GET_SHEET"], data)

    def smartsheet_get_views(self, docid, sheet_id, views_ids=None, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/100228  信息说明
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
        }
        if views_ids:
            data["views_ids"] = views_ids
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_GET_VIEWS"], data)

    def smartsheet_get_fields(self, docid, sheet_id, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/100229
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
        }
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_GET_FIELDS"], data)

    def smartsheet_get_records(self, docid, sheet_id, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/100230
        """
        data = {
            "docid": docid,
            "sheet_id": sheet_id,
            "offset": 0,
            "limit": 1000,
        }
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_SMARTSHEET_GET_RECORDS"], data)

    def smartsheet_get_sheet_priv(self, docid, type, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/100193
        type 权限规则类型, 1: 全员权限; 2: 额外权限
        查询额外权限(type=2)时, 需要添加rule_id_list
        """
        data = {"docid": docid, "type": type}
        data.update(kwargs)
        return self.api.http_call(
            CORP_API_TYPE["WEDOC_SMARTSHEET_GET_SHEET_PRIV"], data
        )

    def get_doc_auth(self, docid):
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_DOC_AUTH"], {"docid": docid})

    def mod_doc_join_rule(self, docid, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97792
        """
        data = {"docid": docid}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_MOD_DOC_JOIN_RULE"], data)

    def mod_doc_member(self, docid, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97795
        """
        data = {"docid": docid}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_MOD_DOC_MEMBER"], data)

    def mod_doc_safety_setting(self, docid, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97797
        """
        data = {"docid": docid}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_MOD_DOC_SAFETY_SETTING"], data)

    def create_form(self, form_info, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97472
        """
        data = {"form_info": form_info}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_CREATE_FORM"], data)

    def modify_form(self, oper, formid, form_info, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97820
        """
        data = {"oper": oper, "formid": formid, "form_info": form_info}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_MODIFY_FORM"], data)

    def get_form_info(self, formid):
        data = {"formid": formid}
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_FORM_INFO"], data)

    def get_form_statistic(self, repeated_id, req_type=1, **kwargs):
        """
        https://developer.work.weixin.qq.com/document/path/97822
        """
        data = {"repeated_id": repeated_id, "req_type": req_type}
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_FORM_STATISTIC"], data)

    def get_form_answer(self, repeated_id, answer_ids):
        """
        https://developer.work.weixin.qq.com/document/path/97823
        """
        data = {"repeated_id": repeated_id, "answer_ids": answer_ids}
        return self.api.http_call(CORP_API_TYPE["WEDOC_GET_FORM_ANSWER"], data)
