"""
pten.wwcontact
~~~~~~~~~~~~

This module implements the Contact class.

"""

from .keys import Keys
from .wwapi import CORP_API_TYPE, CorpApi


def encode_url(url):
    import urllib.parse

    return urllib.parse.quote(url, safe="")


class Contact:
    def __init__(
        self,
        keys_filepath="pten_keys.ini",
        contact_sync_secret=None,
        keys: Keys = None,
        **kwargs,
    ):
        self.keys = keys if keys else Keys(keys_filepath)
        if contact_sync_secret is None:
            contact_sync_secret = self.keys.get_contact_sync_secret()

        self.api = CorpApi(keys_filepath, corpsecret=contact_sync_secret)

    def create_user(self, userid, name, **kwargs):
        data = {}
        data["userid"] = userid
        data["name"] = name
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["USER_CREATE"], data)

    def get_user(self, userid):
        return self.api.http_call(CORP_API_TYPE["USER_GET"], {"userid": userid})

    def update_user(self, userid, **kwargs):
        """
        仅通讯录同步助手或第三方通讯录应用可调用
        """
        data = {}
        data["userid"] = userid
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["USER_UPDATE"], data)

    def delete_user(self, userid):
        """
        仅通讯录同步助手或第三方通讯录应用可调用
        """
        return self.api.http_call(CORP_API_TYPE["USER_DELETE"], {"userid": userid})

    def batch_delete_user(self, useridlist):
        """
        仅通讯录同步助手或第三方通讯录应用可调用
        """
        data = {"useridlist": useridlist}
        return self.api.http_call(CORP_API_TYPE["USER_BATCH_DELETE"], data)

    def get_user_simple_list(self, department_id):
        """
        获取部门成员
        """
        data = {"department_id": department_id}
        return self.api.http_call(CORP_API_TYPE["USER_SIMPLE_LIST"], data)

    def get_user_list(self, department_id):
        """
        获取部门成员详情
        """
        data = {"department_id": department_id}
        return self.api.http_call(CORP_API_TYPE["USER_LIST"], data)

    def convert_userid_to_openid(self, userid):
        return self.api.http_call(CORP_API_TYPE["USERID_TO_OPENID"], {"userid": userid})

    def convert_openid_to_userid(self, openid):
        return self.api.http_call(CORP_API_TYPE["OPENID_TO_USERID"], {"openid": openid})

    def invite_users(self, userlist):
        return self.api.http_call(CORP_API_TYPE["BATCH_INVITE"], {"user": userlist})

    def get_join_qrcode(self, size_type):
        """
        须拥有通讯录的管理权限，使用通讯录同步的Secret。
        """
        data = {"size_type": size_type}
        return self.api.http_call(CORP_API_TYPE["GET_JOIN_QRCODE"], data)

    def get_userid_by_mobile(self, mobile):
        data = {"mobile": mobile}
        return self.api.http_call(CORP_API_TYPE["GET_USERID_BY_MOBILE"], data)

    def get_userid_by_email(self, email):
        return self.api.http_call(
            CORP_API_TYPE["GET_USERID_BY_EMAIL"], {"email": email}
        )

    def get_user_id_list(self):
        """
        仅支持通过“通讯录同步secret”调用。
        """
        return self.api.http_call(CORP_API_TYPE["USER_ID_LIST"])

    def create_department(self, name, parentid, **kwargs):
        """
        第三方仅通讯录应用可以调用。
        """
        data = {"name": name, "parentid": parentid}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_CREATE"], data)

    def update_department(self, id, **kwargs):
        """
        应用须拥有指定部门的管理权限。如若要移动部门，需要有新父部门的管理权限。
        第三方仅通讯录应用可以调用。
        """
        data = {"id": id}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_UPDATE"], data)

    def delete_department(self, id):
        """
        应用须拥有指定部门的管理权限。
        第三方仅通讯录应用可以调用。
        """
        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_DELETE"], {"id": id})

    def get_department_list(self):
        """
        从2022年8月15日10点开始, “企业管理后台 - 管理工具 - 通讯录同步”的新增IP将不能再调用此接口
        企业可通过「获取部门ID列表」接口获取部门ID列表。
        """
        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_LIST"])

    def get_department_simplelist(self):
        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_SIMPLE_LIST"])

    def get_department_detail(self, id):
        """
        从2022年8月15日10点开始, “企业管理后台 - 管理工具 - 通讯录同步”的新增IP将不能再调用此接口
        企业可通过「获取部门ID列表」接口获取部门ID列表。
        """
        return self.api.http_call(CORP_API_TYPE["DEPARTMENT_GET"], {"id": id})

    def create_tag(self, tagname, tagid=None):
        data = {"tagname": tagname}
        if tagid:
            data["tagid"] = tagid

        return self.api.http_call(CORP_API_TYPE["TAG_CREATE"], data)

    def udpate_tag(self, tagname, tagid):
        """
        调用的应用必须是指定标签的创建者。
        """
        data = {"tagid": tagid, "tagname": tagname}
        return self.api.http_call(CORP_API_TYPE["TAG_UPDATE"], data)

    def delete_tag(self, tagid):
        """
        调用的应用必须是指定标签的创建者。
        """
        return self.api.http_call(CORP_API_TYPE["TAG_DELETE"], {"tagid": tagid})

    def get_tag_user(self, tagid):
        """ "
        无限制，但返回列表仅包含应用可见范围的成员；第三方可获取自己创建的标签及应用可见范围内的标签详情
        """
        return self.api.http_call(CORP_API_TYPE["TAG_GET_USER"], {"tagid": tagid})

    def add_tag_user(self, tagid, userlist=None, partylist=None):
        """
        调用的应用必须是指定标签的创建者；成员属于应用的可见范围。
        注意，每个标签下部门数和人员数总和不能超过3万个。
        """
        data = {"tagid": tagid}
        if userlist:
            data["userlist"] = userlist
        if partylist:
            data["partylist"] = partylist

        if not userlist and not partylist:
            raise ValueError("userlist or partylist is required")
        if (len(userlist) > 1000) or (len(partylist) > 100):
            raise ValueError("(len(userlist) > 1000) or (len(partylist) > 100)")

        return self.api.http_call(CORP_API_TYPE["TAG_ADD_USER"], data)

    def delete_tag_user(self, tagid, userlist=None, partylist=None):
        """
        调用的应用必须是指定标签的创建者；成员属于应用的可见范围。
        """
        data = {"tagid": tagid}
        if userlist:
            data["userlist"] = userlist
        if partylist:
            data["partylist"] = partylist

        if not userlist and not partylist:
            raise ValueError("userlist or partylist is required")
        if (len(userlist) > 1000) or (len(partylist) > 100):
            raise ValueError("(len(userlist) > 1000) or (len(partylist) > 100)")

        return self.api.http_call(CORP_API_TYPE["TAG_DELETE_USER"], data)

    def get_tag_list(self):
        """
        自建应用或通讯同步助手可以获取所有标签列表；第三方应用仅可获取自己创建的标签。
        """
        return self.api.http_call(CORP_API_TYPE["TAG_GET_LIST"])

    def batch_sync_users(self, media_id, **kwargs):
        """
        须拥有通讯录的写权限。
        """
        data = {"media_id": media_id}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["BATCH_SYNC_USERS"], data)

    def batch_replace_users(self, media_id, **kwargs):
        """
        须拥有通讯录的写权限。
        """
        data = {"media_id": media_id}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["BATCH_REPLACE_USERS"], data)

    def batch_replace_departments(self, media_id, **kwargs):
        """
        须拥有通讯录的写权限。
        """
        data = {"media_id": media_id}
        data.update(kwargs)

        return self.api.http_call(CORP_API_TYPE["BATCH_REPLACE_PARTY"], data)

    def batch_get_job_result(self, jobid):
        """
        只能查询已经提交过的历史任务。
        """
        data = {"jobid": jobid}
        return self.api.http_call(CORP_API_TYPE["BATCH_JOB_GET_RESULT"], data)

    def export_simple_user(self, encoding_aeskey, block_size=None):
        """
        仅会返回有权限的人员列表
        """
        data = {"encoding_aeskey": encoding_aeskey}
        if block_size:
            data["block_size"] = block_size

        return self.api.http_call(CORP_API_TYPE["EXPORT_SIMPLE_USER"], data)

    def export_user(self, encoding_aeskey, block_size=None):
        """
        仅会返回有权限的人员列表
        """
        data = {"encoding_aeskey": encoding_aeskey}
        if block_size:
            data["block_size"] = block_size

        return self.api.http_call(CORP_API_TYPE["EXPORT_USER"], data)

    def export_department(self, encoding_aeskey, block_size=None):
        """
        仅返回有权限的部门列表
        从2022年8月15日10点开始, “企业管理后台 - 管理工具 - 通讯录同步”的新增IP将不能再调用此接口
        企业可通过「获取成员ID列表」和「获取部门ID列表」接口获取userid和部门ID列表。
        """
        data = {"encoding_aeskey": encoding_aeskey}
        if block_size:
            data["block_size"] = block_size

        return self.api.http_call(CORP_API_TYPE["EXPORT_DEPARTMENT"], data)

    def export_tag_user(self, tagid, encoding_aeskey, block_size=None):
        """
        要求对标签有读取权限
        """
        data = {"tagid": tagid, "encoding_aeskey": encoding_aeskey}
        if block_size:
            data["block_size"] = block_size

        return self.api.http_call(CORP_API_TYPE["EXPORT_TAG_USER"], data)

    def export_get_result(self, jobid):
        """
        获取任务结果的调用身份需要与提交任务的一致
        """
        data = {"jobid": jobid}
        return self.api.http_call(CORP_API_TYPE["EXPORT_GET_RESULT"], data)

    def auth_get_user_info(self, code):
        """
        跳转的域名须完全匹配access_token对应应用的可信域名，否则会返回50001错误。
        """
        return self.api.http_call(CORP_API_TYPE["AUTH_GET_USER_INFO"], {"code": code})

    def auth_get_user_detail(self, user_ticket):
        """
        跳转的域名须完全匹配access_token对应应用的可信域名，否则会返回50001错误。
        """
        data = {"user_ticket": user_ticket}
        return self.api.http_call(CORP_API_TYPE["AUTH_GET_USER_DETAIL"], data)
