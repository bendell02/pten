"""
pten.wwapi
~~~~~~~~~~~~

This module implements the WeWork API. It is from https://github.com/sbzhu/weworkapi_python

"""

from . import base_api, logger
from .base_api import ApiException, make_token_key
from .keys import Keys


class AbstractApi(base_api.AbstractApi):
    """企业微信 API 基类，为共享的 HTTP 管道提供厂商配置。"""

    BASE_URL = "https://qyapi.weixin.qq.com"
    RESPONSE_CODE_FIELD = "errcode"
    RESPONSE_MSG_FIELD = "errmsg"
    # SUITE_ACCESS_TOKEN 必须排在 ACCESS_TOKEN 之前（前者包含后者作为子串）；
    # _append_token / _refresh_token 取第一个匹配项。
    TOKEN_PLACEHOLDERS = (
        ("SUITE_ACCESS_TOKEN", "get_suite_access_token"),
        ("PROVIDER_ACCESS_TOKEN", "get_provider_access_token"),
        ("ACCESS_TOKEN", "get_access_token"),
        ("WEBHOOK_KEY", "get_bot_webhook_key"),
    )
    TOKEN_EXPIRED_CODES = (40014, 42001, 42007, 42009)

    def _debug_url(self, url):
        return url + "&debug=1"


BOT_API_TYPE = {
    # bot using webhook key. No access_token
    "WEBHOOK_SEND": ["/cgi-bin/webhook/send?key=WEBHOOK_KEY", "POST"],
    "WEBHOOK_MEDIA_UPLOAD": [
        "/cgi-bin/webhook/upload_media?key=WEBHOOK_KEY",
        "POST_FILE",
    ],
}


class BotApi(AbstractApi):
    def __init__(
        self, keys_filepath="pten_keys.ini", webhook_key=None, keys: Keys = None
    ):
        super().__init__(keys_filepath, keys=keys)
        if webhook_key is not None:
            self.webhook_key = webhook_key
        else:
            self.webhook_key = self.keys.get_bot_weebhook_key()

    def get_bot_webhook_key(self):
        return self.webhook_key


CORP_API_TYPE = {
    "GET_ACCESS_TOKEN": ["/cgi-bin/gettoken", "GET"],
    # user
    "USER_CREATE": ["/cgi-bin/user/create?access_token=ACCESS_TOKEN", "POST"],
    "USER_GET": ["/cgi-bin/user/get?access_token=ACCESS_TOKEN", "GET"],
    "USER_UPDATE": ["/cgi-bin/user/update?access_token=ACCESS_TOKEN", "POST"],
    "USER_DELETE": ["/cgi-bin/user/delete?access_token=ACCESS_TOKEN", "GET"],
    "USER_BATCH_DELETE": [
        "/cgi-bin/user/batchdelete?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "USER_SIMPLE_LIST": ["/cgi-bin/user/simplelist?access_token=ACCESS_TOKEN", "GET"],
    "USER_LIST": ["/cgi-bin/user/list?access_token=ACCESS_TOKEN", "GET"],
    "USERID_TO_OPENID": [
        "/cgi-bin/user/convert_to_openid?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "OPENID_TO_USERID": [
        "/cgi-bin/user/convert_to_userid?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "GET_USERID_BY_MOBILE": [
        "cgi-bin/user/getuserid?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "GET_USERID_BY_EMAIL": [
        "cgi-bin/user/get_userid_by_email?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "USER_ID_LIST": [
        "cgi-bin/user/list_id?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "USER_AUTH_SUCCESS": ["/cgi-bin/user/authsucc?access_token=ACCESS_TOKEN", "GET"],
    "GET_USER_INFO_BY_CODE": [
        "/cgi-bin/user/getuserinfo?access_token=ACCESS_TOKEN",
        "GET",
    ],
    "GET_USER_DETAIL": [
        "/cgi-bin/user/getuserdetail?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # department
    "DEPARTMENT_CREATE": [
        "/cgi-bin/department/create?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "DEPARTMENT_UPDATE": [
        "/cgi-bin/department/update?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "DEPARTMENT_DELETE": [
        "/cgi-bin/department/delete?access_token=ACCESS_TOKEN",
        "GET",
    ],
    "DEPARTMENT_LIST": ["/cgi-bin/department/list?access_token=ACCESS_TOKEN", "GET"],
    "DEPARTMENT_SIMPLE_LIST": [
        "/cgi-bin/department/simplelist?access_token=ACCESS_TOKEN",
        "GET",
    ],
    "DEPARTMENT_GET": ["/cgi-bin/department/get?access_token=ACCESS_TOKEN", "GET"],
    # tag
    "TAG_CREATE": ["/cgi-bin/tag/create?access_token=ACCESS_TOKEN", "POST"],
    "TAG_UPDATE": ["/cgi-bin/tag/update?access_token=ACCESS_TOKEN", "POST"],
    "TAG_DELETE": ["/cgi-bin/tag/delete?access_token=ACCESS_TOKEN", "GET"],
    "TAG_GET_USER": ["/cgi-bin/tag/get?access_token=ACCESS_TOKEN", "GET"],
    "TAG_ADD_USER": ["/cgi-bin/tag/addtagusers?access_token=ACCESS_TOKEN", "POST"],
    "TAG_DELETE_USER": ["/cgi-bin/tag/deltagusers?access_token=ACCESS_TOKEN", "POST"],
    "TAG_GET_LIST": ["/cgi-bin/tag/list?access_token=ACCESS_TOKEN", "GET"],
    # batch
    "BATCH_INVITE": ["/cgi-bin/batch/invite?access_token=ACCESS_TOKEN", "POST"],
    "BATCH_SYNC_USERS": ["/cgi-bin/batch/syncuser?access_token=ACCESS_TOKEN", "POST"],
    "BATCH_REPLACE_USERS": [
        "/cgi-bin/batch/replaceuser?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "BATCH_REPLACE_PARTY": [
        "/cgi-bin/batch/replaceparty?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "BATCH_JOB_GET_RESULT": [
        "/cgi-bin/batch/getresult?access_token=ACCESS_TOKEN",
        "GET",
    ],
    # export
    "EXPORT_SIMPLE_USER": [
        "/cgi-bin/export/simple_user?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "EXPORT_USER": [
        "/cgi-bin/export/user?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "EXPORT_DEPARTMENT": [
        "/cgi-bin/export/department?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "EXPORT_TAG_USER": [
        "/cgi-bin/export/taguser?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "EXPORT_GET_RESULT": [
        "/cgi-bin/export/get_result?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # auth
    "AUTH_GET_USER_INFO": [
        "/cgi-bin/auth/getuserinfo?access_token=ACCESS_TOKEN",
        "GET",
    ],
    "AUTH_GET_USER_DETAIL": [
        "/cgi-bin/auth/getuserdetail?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # agent
    "AGENT_GET": ["/cgi-bin/agent/get?access_token=ACCESS_TOKEN", "GET"],
    "AGENT_SET": ["/cgi-bin/agent/set?access_token=ACCESS_TOKEN", "POST"],
    "AGENT_GET_LIST": ["/cgi-bin/agent/list?access_token=ACCESS_TOKEN", "GET"],
    # menu
    "MENU_CREATE": ["/cgi-bin/menu/create?access_token=ACCESS_TOKEN", "POST"],
    "MENU_GET": ["/cgi-bin/menu/get?access_token=ACCESS_TOKEN", "GET"],
    "MENU_DELETE": ["/cgi-bin/menu/delete?access_token=ACCESS_TOKEN", "GET"],
    # message
    "MESSAGE_SEND": ["/cgi-bin/message/send?access_token=ACCESS_TOKEN", "POST"],
    "MESSAGE_REVOKE": ["/cgi-bin/message/revoke?access_token=ACCESS_TOKEN", "POST"],
    # media
    "MEDIA_GET": ["/cgi-bin/media/get?access_token=ACCESS_TOKEN", "GET"],
    "MEDIA_UPLOAD": ["/cgi-bin/media/upload?access_token=ACCESS_TOKEN", "POST_FILE"],
    # ticket
    "GET_TICKET": ["/cgi-bin/ticket/get?access_token=ACCESS_TOKEN", "GET"],
    "GET_JSAPI_TICKET": ["/cgi-bin/get_jsapi_ticket?access_token=ACCESS_TOKEN", "GET"],
    # checkin
    "GET_CHECKIN_OPTION": [
        "/cgi-bin/checkin/getcheckinoption?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "GET_CHECKIN_DATA": [
        "/cgi-bin/checkin/getcheckindata?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # corp
    "GET_JOIN_QRCODE": [
        "/cgi-bin/corp/get_join_qrcode?access_token=ACCESS_TOKEN",
        "GET",
    ],
    "GET_APPROVAL_DATA": [
        "/cgi-bin/corp/getapprovaldata?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # card
    "GET_INVOICE_INFO": [
        "/cgi-bin/card/invoice/reimburse/getinvoiceinfo?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "UPDATE_INVOICE_STATUS": [
        "/cgi-bin/card/invoice/reimburse/updateinvoicestatus?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "BATCH_UPDATE_INVOICE_STATUS": [
        "/cgi-bin/card/invoice/reimburse/updatestatusbatch?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "BATCH_GET_INVOICE_INFO": [
        "/cgi-bin/card/invoice/reimburse/getinvoiceinfobatch?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # appchat
    "APP_CHAT_CREATE": ["/cgi-bin/appchat/create?access_token=ACCESS_TOKEN", "POST"],
    "APP_CHAT_GET": ["/cgi-bin/appchat/get?access_token=ACCESS_TOKEN", "GET"],
    "APP_CHAT_UPDATE": ["/cgi-bin/appchat/update?access_token=ACCESS_TOKEN", "POST"],
    "APP_CHAT_SEND": ["/cgi-bin/appchat/send?access_token=ACCESS_TOKEN", "POST"],
    # miniprogram
    "MINIPROGRAM_CODE_TO_SESSION_KEY": [
        "/cgi-bin/miniprogram/jscode2session?access_token=ACCESS_TOKEN",
        "GET",
    ],
    # wedoc
    "WEDOC_CREATE": ["/cgi-bin/wedoc/create_doc?access_token=ACCESS_TOKEN", "POST"],
    "WEDOC_RENAME": ["/cgi-bin/wedoc/rename_doc?access_token=ACCESS_TOKEN", "POST"],
    "WEDOC_DELETE": ["/cgi-bin/wedoc/del_doc?access_token=ACCESS_TOKEN", "POST"],
    "WEDOC_GET_BASIC_INFO": [
        "/cgi-bin/wedoc/get_doc_base_info?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SHARE": ["/cgi-bin/wedoc/doc_share?access_token=ACCESS_TOKEN", "POST"],
    "WEDOC_BATCH_UPDATE": [
        "/cgi-bin/wedoc/document/batch_update?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_GET_DOC": ["/cgi-bin/wedoc/document/get?access_token=ACCESS_TOKEN", "POST"],
    "WEDOC_SPREADSHEET_BATCH_UPDATE": [
        "/cgi-bin/wedoc/spreadsheet/batch_update?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SPREADSHEET_GET_RANGE_DATA": [
        "/cgi-bin/wedoc/spreadsheet/get_sheet_range_data?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SPREADSHEET_GET_PROPERTITIES": [
        "/cgi-bin/wedoc/spreadsheet/get_sheet_properties?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_ADD_SHEET": [
        "/cgi-bin/wedoc/smartsheet/add_sheet?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_DELETE_SHEET": [
        "/cgi-bin/wedoc/smartsheet/delete_sheet?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_UPDATE_SHEET": [
        "/cgi-bin/wedoc/smartsheet/update_sheet?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_ADD_VIEW": [
        "/cgi-bin/wedoc/smartsheet/add_view?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_DELETE_VIEW": [
        "/cgi-bin/wedoc/smartsheet/delete_views?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_UPDATE_VIEW": [
        "/cgi-bin/wedoc/smartsheet/update_view?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_ADD_FIELDS": [
        "/cgi-bin/wedoc/smartsheet/add_fields?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_DELETE_FIELDS": [
        "/cgi-bin/wedoc/smartsheet/delete_fields?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_UPDATE_FIELDS": [
        "/cgi-bin/wedoc/smartsheet/update_fields?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_ADD_RECORDS": [
        "/cgi-bin/wedoc/smartsheet/add_records?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_DELETE_RECORDS": [
        "/cgi-bin/wedoc/smartsheet/delete_records?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_UPDATE_RECORDS": [
        "/cgi-bin/wedoc/smartsheet/update_records?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_GET_SHEET": [
        "/cgi-bin/wedoc/smartsheet/get_sheet?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_GET_VIEWS": [
        "/cgi-bin/wedoc/smartsheet/get_views?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_GET_FIELDS": [
        "/cgi-bin/wedoc/smartsheet/get_fields?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_GET_RECORDS": [
        "/cgi-bin/wedoc/smartsheet/get_records?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_SMARTSHEET_GET_SHEET_PRIV": [
        "/cgi-bin/wedoc/smartsheet/content_priv/get_sheet_priv?access_token=ACCESS_TOKEN",
        "POST",
    ],
    # smartsheet/content_priv 还有好几个接口这里没有添加进来，有需要可以参考下面的链接来添加
    # https://developer.work.weixin.qq.com/document/path/100193
    "WEDOC_GET_DOC_AUTH": [
        "/cgi-bin/wedoc/doc_get_auth?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_MOD_DOC_JOIN_RULE": [
        "/cgi-bin/wedoc/mod_doc_join_rule?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_MOD_DOC_MEMBER": [
        "/cgi-bin/wedoc/mod_doc_member?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_MOD_DOC_SAFETY_SETTING": [
        "/cgi-bin/wedoc/mod_doc_safty_setting?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_CREATE_FORM": [
        "/cgi-bin/wedoc/create_form?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_MODIFY_FORM": [
        "/cgi-bin/wedoc/modify_form?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_GET_FORM_INFO": [
        "/cgi-bin/wedoc/get_form_info?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_GET_FORM_STATISTIC": [
        "/cgi-bin/wedoc/get_form_statistic?access_token=ACCESS_TOKEN",
        "POST",
    ],
    "WEDOC_GET_FORM_ANSWER": [
        "/cgi-bin/wedoc/get_form_answer?access_token=ACCESS_TOKEN",
        "POST",
    ],
}


class CorpApi(AbstractApi):
    def __init__(
        self,
        keys_filepath="pten_keys.ini",
        corpid=None,
        corpsecret=None,
        keys: Keys = None,
    ):
        super().__init__(keys_filepath, keys=keys)
        self.corpid = corpid if corpid else self.keys.get_key("ww", "corpid")
        corpsecret_in_file = self.keys.get_key("ww", "app_secret")
        self.corpsecret = corpsecret if corpsecret else corpsecret_in_file

        self._token_key = make_token_key("ww_", self.corpid, self.corpsecret)

    def get_access_token(self):
        try:
            return self.keys.get_access_token(self._token_key)
        except Exception as e:
            logger.warning(f"{str(e)} refreshing access token...")
            return self.refresh_access_token()

    def refresh_access_token(self):
        response = self.http_call(
            CORP_API_TYPE["GET_ACCESS_TOKEN"],
            {
                "corpid": self.corpid,
                "corpsecret": self.corpsecret,
            },
        )
        access_token = response.get("access_token")
        self.keys.save_access_token(self._token_key, access_token)

        return access_token

    def get_corp_jsapi_ticket(self):
        try:
            return self.keys.get_corp_jsapi_ticket(self._token_key)
        except Exception as e:
            logger.warning(f"{str(e)} refreshing corp jsapi ticket...")
            return self.refresh_corp_jsapi_ticket()

    def refresh_corp_jsapi_ticket(self):
        response = self.http_call(CORP_API_TYPE["GET_JSAPI_TICKET"])
        corp_jsapi_ticket = response.get("ticket")
        self.keys.save_corp_jsapi_ticket(self._token_key, corp_jsapi_ticket)

        return corp_jsapi_ticket

    def get_app_jsapi_ticket(self):
        try:
            return self.keys.get_app_jsapi_ticket(self._token_key)
        except Exception as e:
            logger.warning(f"{str(e)} refreshing app jsapi ticket...")
            return self.refresh_app_jsapi_ticket()

    def refresh_app_jsapi_ticket(self):
        response = self.http_call(CORP_API_TYPE["GET_TICKET"], {"type": "agent_config"})
        app_jsapi_ticket = response.get("ticket")
        self.keys.save_app_jsapi_ticket(self._token_key, app_jsapi_ticket)

        return app_jsapi_ticket


SERVICE_CORP_API_TYPE = {
    "GET_CORP_TOKEN": [
        "/cgi-bin/service/get_corp_token?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
    "GET_SUITE_TOKEN": ["/cgi-bin/service/get_suite_token", "POST"],
    "GET_PRE_AUTH_CODE": [
        "/cgi-bin/service/get_pre_auth_code?suite_access_token=SUITE_ACCESS_TOKEN",
        "GET",
    ],
    "SET_SESSION_INFO": [
        "/cgi-bin/service/set_session_info?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
    "GET_PERMANENT_CODE": [
        "/cgi-bin/service/get_permanent_code?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
    "GET_AUTH_INFO": [
        "/cgi-bin/service/get_auth_info?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
    "GET_ADMIN_LIST": [
        "/cgi-bin/service/get_admin_list?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
    "GET_USER_INFO_BY_3RD": [
        "/cgi-bin/service/getuserinfo3rd?suite_access_token=SUITE_ACCESS_TOKEN",
        "GET",
    ],
    "GET_USER_DETAIL_BY_3RD": [
        "/cgi-bin/service/getuserdetail3rd?suite_access_token=SUITE_ACCESS_TOKEN",
        "POST",
    ],
}


class ServiceCorpApi(CorpApi):
    def __init__(
        self,
        suite_id,
        suite_secret,
        suite_ticket,
        keys_filepath="pten_keys.ini",
        keys: Keys = None,
        auth_corpid=None,
        permanent_code=None,
    ):
        super().__init__(keys_filepath, keys=keys)
        self.suite_id = suite_id
        self.suite_secret = suite_secret
        self.suite_ticket = suite_ticket

        # 调用 CorpAPI 的function， 需要设置这两个参数
        self.auth_corpid = auth_corpid
        self.permanent_code = permanent_code

        self.access_token = None
        self.suite_access_token = None

    ## override CorpApi 的 refreshAccessToken， 使用第三方服务商的方法
    def get_access_token(self):
        if self.access_token is None:
            self.refresh_access_token()
        return self.access_token

    def refresh_access_token(self):
        response = self.http_call(
            SERVICE_CORP_API_TYPE["GET_CORP_TOKEN"],
            {
                "auth_corpid": self.auth_corpid,
                "permanent_code": self.permanent_code,
            },
        )
        self.access_token = response.get("access_token")

    ##
    def get_suite_access_token(self):
        if self.suite_access_token is None:
            self.refresh_suite_access_token()
        return self.suite_access_token

    def refresh_suite_access_token(self):
        response = self.http_call(
            SERVICE_CORP_API_TYPE["GET_SUITE_TOKEN"],
            {
                "suite_id": self.suite_id,
                "suite_secret": self.suite_secret,
                "suite_ticket": self.suite_ticket,
            },
        )
        self.suite_access_token = response.get("suite_access_token")


SERVICE_PROVIDER_API_TYPE = {
    "GET_PROVIDER_TOKEN": ["/cgi-bin/service/get_provider_token", "POST"],
    "GET_LOGIN_INFO": [
        "/cgi-bin/service/get_login_info?access_token=PROVIDER_ACCESS_TOKEN",
        "POST",
    ],
    "GET_REGISTER_CODE": [
        "/cgi-bin/service/get_register_code?provider_access_token=PROVIDER_ACCESS_TOKEN",
        "POST",
    ],
    "GET_REGISTER_INFO": [
        "/cgi-bin/service/get_register_info?provider_access_token=PROVIDER_ACCESS_TOKEN",
        "POST",
    ],
    "SET_AGENT_SCOPE": ["/cgi-bin/agent/set_scope", "POST"],
    "SET_CONTACT_SYNC_SUCCESS": ["/cgi-bin/sync/contact_sync_success", "GET"],
}


class ServiceProviderApi(AbstractApi):
    def __init__(
        self, corpid, provider_secret, keys_filepath="pten_keys.ini", keys: Keys = None
    ):
        super().__init__(keys_filepath, keys=keys)
        self.corpid = corpid
        self.provider_secret = provider_secret
        self.provider_access_token = None

    def get_provider_access_token(self):
        if self.provider_access_token is None:
            self.refresh_provider_access_token()
        return self.provider_access_token

    def refresh_provider_access_token(self):
        response = self.http_call(
            SERVICE_PROVIDER_API_TYPE["GET_PROVIDER_TOKEN"],
            {
                "corpid": self.corpid,
                "provider_secret": self.provider_secret,
            },
        )
        self.provider_access_token = response.get("provider_access_token")
