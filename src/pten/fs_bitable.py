"""
pten.fs_bitable
~~~~~~~~~~~~~~~

飞书多维表格（Base）的高层封装：创建多维表格 / 新增数据表 / 新增记录 / 删除记录。
鉴权由 FsCorpApi 的 tenant_access_token 经 Authorization 请求头完成。
"""

from .fs_api import CORP_API_TYPE, FsCorpApi
from .keys import Keys


class FsBitable:
    """飞书多维表格客户端，封装常用写操作。

    :param keys_filepath: 配置文件路径，缺省 pten_keys.ini
    :param keys: 共享 Keys 实例，可跨模块注入以复用 token 缓存
    """

    def __init__(self, keys_filepath="pten_keys.ini", keys: Keys = None, **kwargs):
        self.keys = keys if keys else Keys(keys_filepath)
        self.api = FsCorpApi(keys_filepath, keys=keys)

    @staticmethod
    def _sub(url, **mapping):
        """把 URL 里的路径占位符（APP_TOKEN/TABLE_ID/RECORD_ID）替换为实参。"""
        for placeholder, value in mapping.items():
            url = url.replace(placeholder, value)
        return url

    def create_app(self, name=None, folder_token=None, time_zone=None, **kwargs):
        """创建一个多维表格（含一张空数据表）。

        :param name: 多维表格名称，最长 255 字符，缺省由服务端命名
        :param folder_token: 归属文件夹 token，缺省创建在云空间根目录
        :param time_zone: 文档时区，如 "Asia/Shanghai"
        :return: data.app 含 app_token / default_table_id / url / name / folder_token
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app/create
        """
        data = {}
        if name:
            data["name"] = name
        if folder_token:
            data["folder_token"] = folder_token
        if time_zone:
            data["time_zone"] = time_zone
        data.update(kwargs)
        return self.api.http_call(CORP_API_TYPE["BITABLE_APP_CREATE"], data)

    def create_table(
        self, app_token, name, fields=None, default_view_name=None, **kwargs
    ):
        """在指定多维表格下新增一个数据表。

        :param app_token: 目标多维表格 app_token
        :param name: 数据表名称（1~100 字符；不可含 / \\ ? * : [ ] ）
        :param fields: 初始字段列表，每项 {field_name, type, ui_type?, property?}；
            首字段须为索引字段（type 仅支持 1文本/2数字/5日期/13电话/15超链接/20公式/22地理位置）；
            缺省则创建仅含索引字段的空表
        :param default_view_name: 默认视图名；传入时 fields 必须同时传入
        :return: data 含 table_id（以及 default_view_id / field_id_list）
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/create
        """
        table = {"name": name}
        if default_view_name:
            table["default_view_name"] = default_view_name
        if fields:
            table["fields"] = fields
        table.update(kwargs)
        shortUrl, method = CORP_API_TYPE["BITABLE_TABLE_CREATE"]
        url = self._sub(shortUrl, APP_TOKEN=app_token)
        return self.api.http_call([url, method], {"table": table})

    def list_tables(self, app_token, page_size=None, page_token=None, **kwargs):
        """列出多维表格中的所有数据表。

        :param app_token: 多维表格 app_token
        :param page_size: 分页大小，默认 20，最大 100
        :param page_token: 分页标记，第一次不填表示从头遍历；响应 has_more=True 时返回新 page_token
        :return: data 含 has_more / page_token / total / items（每项含 table_id、name、revision）
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/list
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_TABLE_LIST"]
        url = self._sub(shortUrl, APP_TOKEN=app_token)
        args = {}
        if page_size is not None:
            args["page_size"] = str(page_size)
        if page_token:
            args["page_token"] = page_token
        args.update(kwargs)
        return self.api.http_call([url, method], args)

    def delete_table(self, app_token, table_id, **kwargs):
        """删除一个数据表（多维表格中只剩最后一张表时不允许删除）。

        :param app_token: 多维表格 app_token
        :param table_id: 待删数据表 table_id
        :return: data 为空 dict（成功即 code==0）
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/delete
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_TABLE_DELETE"]
        url = self._sub(shortUrl, APP_TOKEN=app_token, TABLE_ID=table_id)
        # DELETE 无请求体；kwargs 留作可能的查询参数扩展
        return self.api.http_call([url, method], kwargs)

    def create_record(
        self,
        app_token,
        table_id,
        fields,
        user_id_type=None,
        client_token=None,
        ignore_consistency_check=None,
        **kwargs,
    ):
        """新增一条记录。

        :param app_token: 多维表格 app_token
        :param table_id: 数据表 table_id
        :param fields: 记录数据，键为字段名，值为该字段类型对应的数据
            （文本→str；数字→num；单选→选项str；多选→list[str]；日期→毫秒时间戳；
            复选→bool；人员→[{"id": ...}]；超链接→{"text","link"}；附件→[{"file_token":...}]；
            单/双向关联→[record_id, ...]；地理位置→"lng,lat"）
        :param user_id_type: 人员字段 ID 类型 open_id/union_id/user_id，缺省 open_id（服务端默认）
        :param client_token: uuidv4 幂等键，缺省不发（每次均为新请求）
        :param ignore_consistency_check: 是否忽略一致性读写检查
        :return: data.record 含 record_id / id / fields
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_RECORD_CREATE"]
        url = self._sub(shortUrl, APP_TOKEN=app_token, TABLE_ID=table_id)
        # POST 的 args 进请求体，查询参数必须走 URL；复用 _append_args 拼 ?/&
        query = {}
        if user_id_type:
            query["user_id_type"] = user_id_type
        if client_token:
            query["client_token"] = client_token
        if ignore_consistency_check is not None:
            query["ignore_consistency_check"] = str(ignore_consistency_check).lower()
        if query:
            url = self.api._append_args(url, query)
        data = {"fields": fields}
        data.update(kwargs)
        return self.api.http_call([url, method], data)

    def delete_record(
        self, app_token, table_id, record_id, ignore_consistency_check=None, **kwargs
    ):
        """删除一条记录。

        :param app_token: 多维表格 app_token
        :param table_id: 数据表 table_id
        :param record_id: 待删记录的 record_id
        :param ignore_consistency_check: 是否忽略一致性读写检查
        :return: data 含 deleted（bool）/ record_id
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/delete
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_RECORD_DELETE"]
        url = self._sub(
            shortUrl, APP_TOKEN=app_token, TABLE_ID=table_id, RECORD_ID=record_id
        )
        args = {}
        if ignore_consistency_check is not None:
            args["ignore_consistency_check"] = str(ignore_consistency_check).lower()
        args.update(kwargs)
        # DELETE 分支用 _append_args 把 args 拼成查询串；无 body
        return self.api.http_call([url, method], args)

    def update_record(
        self,
        app_token,
        table_id,
        record_id,
        fields,
        user_id_type=None,
        ignore_consistency_check=None,
        **kwargs,
    ):
        """更新一条记录（增量更新，仅更新传入的字段；置空传 null）。

        :param app_token: 多维表格 app_token
        :param table_id: 数据表 table_id
        :param record_id: 待更新记录的 record_id
        :param fields: 要更新的字段数据，键为字段名（字段值类型同 create_record）
        :param user_id_type: 人员字段 ID 类型 open_id/union_id/user_id，缺省 open_id
        :param ignore_consistency_check: 是否忽略一致性读写检查
        :return: data.record 含 record_id / id / fields
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_RECORD_UPDATE"]
        url = self._sub(
            shortUrl, APP_TOKEN=app_token, TABLE_ID=table_id, RECORD_ID=record_id
        )
        # PUT 的 args 进请求体（同 POST），查询参数必须走 URL
        query = {}
        if user_id_type:
            query["user_id_type"] = user_id_type
        if ignore_consistency_check is not None:
            query["ignore_consistency_check"] = str(ignore_consistency_check).lower()
        if query:
            url = self.api._append_args(url, query)
        data = {"fields": fields}
        data.update(kwargs)
        return self.api.http_call([url, method], data)
