"""
pten.fs_bitable
~~~~~~~~~~~~~~~

飞书多维表格（Base）的高层封装：多维表格 / 数据表 / 记录的增删改查。
鉴权由 FsCorpApi 的 tenant_access_token 经 Authorization 请求头完成。
字段类型枚举 :class:`FsFieldType` 映射服务端的 type 数字，供数据表 fields 的 type 使用。
"""

from enum import IntEnum

from .fs_api import CORP_API_TYPE, FsCorpApi
from .keys import Keys


class FsFieldType(IntEnum):
    """飞书多维表格字段类型，映射服务端 ``type`` 数字。

    IntEnum 与裸数字等价（``FsFieldType.TEXT == 1``）：放进 fields 的 type
    经 JSON 序列化后仍是数字，也兼容直接传裸数字的旧写法。

    :ivar READONLY_TYPES: 只读字段类型集合（系统字段 / 公式 / 查找引用 / 按钮 / 流程），
        写接口不支持新增或编辑这些字段的值；供 :meth:`FsBitable.validate_record_fields`
        等做写前预检。

    https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/guide
    """

    TEXT = 1  # 多行文本（ui_type 另可 Barcode 条码 / Email 邮箱）
    NUMBER = 2  # 数字（ui_type 另可 Progress 进度 / Currency 货币 / Rating 评分）
    SINGLE_SELECT = 3  # 单选
    MULTI_SELECT = 4  # 多选
    DATETIME = 5  # 日期
    CHECKBOX = 7  # 复选框
    USER = 11  # 人员
    PHONE = 13  # 电话号码
    URL = 15  # 超链接
    ATTACHMENT = 17  # 附件
    SINGLE_LINK = 18  # 单向关联
    LOOKUP = 19  # 查找引用（只读，写接口不支持新增或编辑）
    FORMULA = 20  # 公式（只读，写接口不支持新增或编辑）
    DUPLEX_LINK = 21  # 双向关联
    LOCATION = 22  # 地理位置
    GROUP_CHAT = 23  # 群组
    WORKFLOW = 24  # 流程（只读，写接口不支持新增或编辑）
    CREATED_TIME = 1001  # 创建时间（系统字段，只读）
    MODIFIED_TIME = 1002  # 最后更新时间（系统字段，只读）
    CREATED_USER = 1003  # 创建人（系统字段，只读）
    MODIFIED_USER = 1004  # 修改人（系统字段，只读）
    AUTO_NUMBER = 1005  # 自动编号（系统字段，只读）
    BUTTON = 3001  # 按钮（只读，写接口不支持新增或编辑）


# 只读字段类型：系统字段 / 公式 / 查找引用 / 按钮 / 流程
# （写接口不支持新增或编辑，写入必被服务端拒绝；与各成员注释同源）
# 作为类属性挂在 enum 上：不能放进类体——IntEnum 会把 frozenset 当作成员并尝试
# int() 化其值，触发 TypeError；类外赋值则只是普通类属性，不参与成员解析
FsFieldType.READONLY_TYPES = frozenset(
    {
        FsFieldType.LOOKUP,
        FsFieldType.FORMULA,
        FsFieldType.CREATED_TIME,
        FsFieldType.MODIFIED_TIME,
        FsFieldType.CREATED_USER,
        FsFieldType.MODIFIED_USER,
        FsFieldType.AUTO_NUMBER,
        FsFieldType.BUTTON,
        FsFieldType.WORKFLOW,
    }
)


class FsBitable:
    """飞书多维表格客户端，封装常用读写操作及字段校验。

    :param keys_filepath: 配置文件路径，缺省按 Keys 的查找链解析（见 :class:`pten.keys.Keys`）
    :param keys: 共享 Keys 实例，可跨模块注入以复用 token 缓存
    """

    def __init__(self, keys_filepath=None, keys: Keys = None, **kwargs):
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
            type 传 FsFieldType 枚举或裸数字均可（两者等价）；
            首字段须为索引字段（仅支持 FsFieldType 的
            TEXT/NUMBER/DATETIME/PHONE/URL/FORMULA/LOCATION）；
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

    def list_fields(
        self,
        app_token,
        table_id,
        page_size=None,
        page_token=None,
        view_id=None,
        text_field_as_array=None,
        **kwargs,
    ):
        """列出数据表中的字段（含字段名 / type / ui_type / property / is_primary 等）。

        :param app_token: 多维表格 app_token
        :param table_id: 数据表 table_id
        :param page_size: 分页大小，默认 20，最大 100
        :param page_token: 分页标记，第一次不填表示从头遍历；has_more=True 时返回新 page_token
        :param view_id: 视图 ID，限定某视图下的字段；不传返回全部字段
        :param text_field_as_array: True 时 description 以数组形式返回，缺省 False
        :return: data 含 has_more / page_token / total / items（每项含 field_id / field_name /
            type / ui_type / property / is_primary / is_hidden）
        https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/list
        """
        shortUrl, method = CORP_API_TYPE["BITABLE_FIELD_LIST"]
        url = self._sub(shortUrl, APP_TOKEN=app_token, TABLE_ID=table_id)
        args = {}
        if page_size is not None:
            args["page_size"] = str(page_size)
        if page_token:
            args["page_token"] = page_token
        if view_id:
            args["view_id"] = view_id
        if text_field_as_array is not None:
            # 布尔须转小写 true/false，否则服务端拿到 Python 的 True/False 不认
            args["text_field_as_array"] = str(text_field_as_array).lower()
        args.update(kwargs)
        return self.api.http_call([url, method], args)

    @staticmethod
    def _check_value_type(name, ftype, value):
        """对标量字段类型的取值形状做本地预检，返回问题描述列表。

        只覆盖取值契约无歧义的标量类型（数字 / 日期 / 复选框）；文本、选项、
        人员、关联等类型的取值形状复杂或服务端可宽容处理，留给服务端判定，
        避免本地预检误伤合法写入。bool 是 int 的子类，须先排除，
        否则 True/False 会被当成数字/时间戳放行。
        """
        if value is None:
            # None 表示不写该字段，形状交给服务端判定
            return []
        issues = []
        if ftype == FsFieldType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                issue = f"字段「{name}」为数字字段，值应为数字，当前为 {type(value).__name__}：{value!r}"
                issues.append(issue)
        elif ftype == FsFieldType.DATETIME:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                issue = f"字段「{name}」为日期字段，值应为毫秒时间戳（如 int(time.time() * 1000)），当前为 {type(value).__name__}：{value!r}"
                issues.append(issue)
        elif ftype == FsFieldType.CHECKBOX:
            if not isinstance(value, bool):
                issue = f"字段「{name}」为复选框字段，值应为 bool，当前为 {type(value).__name__}：{value!r}"
                issues.append(issue)
        return issues

    def validate_record_fields(
        self,
        app_token,
        table_id,
        fields,
        view_id=None,
        raise_on_error=True,
    ):
        """校验待写入记录的字段是否符合数据表定义（本地预检，不发写请求）。

        自动翻页拉取数据表全部字段后逐项检查：
          1) 未知字段——字段名不在数据表中；
          2) 只读字段——字段为系统/公式/查找引用/按钮/流程等不可写类型；
          3) 取值形状——数字/日期/复选框等标量字段的值类型不符。

        :param app_token: 多维表格 app_token
        :param table_id: 数据表 table_id
        :param fields: 待校验的记录数据，键为字段名（形状同 create_record 的 fields）
        :param view_id: 限定按某视图的字段集合校验，不传用全部字段
        :param raise_on_error: True（默认）时校验不过抛 ValueError；False 时仅返回问题列表
        :return: 问题字符串列表，空列表表示全部通过
        """
        if not fields:  # 无待校验字段，直接放行，避免白跑一次拉取
            return []
        # 自动翻页聚合全量字段（field_name -> item）
        field_map = {}
        page_token = None
        while True:
            res = self.list_fields(
                app_token,
                table_id,
                page_size=100,
                page_token=page_token,
                view_id=view_id,
            )
            for item in res["data"].get("items", []):
                field_map[item["field_name"]] = item
            if not res["data"].get("has_more"):
                break
            next_token = res["data"].get("page_token")
            # has_more=True 但未返回有效的下一页 token（或 token 未变化）时，
            # 继续翻只会重复拉同一页 → 死循环，主动中断
            if not next_token or next_token == page_token:
                break
            page_token = next_token

        # 逐项校验：未知字段 / 只读字段 / 标量取值形状
        issues = []
        for name, value in fields.items():
            item = field_map.get(name)
            if item is None:
                issues.append(f"未知字段「{name}」：数据表中不存在该字段")
                continue
            ftype = item.get("type")
            # IntEnum 与裸 int 等价（FsFieldType.FORMULA == 20 且哈希相同），
            # 服务端返回的 int type 可直接命中 FsFieldType.READONLY_TYPES
            if ftype in FsFieldType.READONLY_TYPES:
                issue = f"字段「{name}」为只读/系统字段（type={int(ftype)}），不可写入"
                issues.append(issue)
                continue
            issues.extend(self._check_value_type(name, ftype, value))

        if issues and raise_on_error:
            raise ValueError("字段校验未通过：\n  " + "\n  ".join(issues))
        return issues

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
