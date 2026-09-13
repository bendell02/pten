"""飞书多维表格（Base）增删改查示例。

运行前提：[fs] 配置 app_id、app_secret。
注意：本例会真实创建一个多维表格并增删数据。结束时只删除本例创建的记录和数据表，
多维表格本身会保留（可在飞书云空间手动删除）；想保留全部数据观察效果的话，
注释掉最后的删除步骤即可。
运行方式：python examples/fs/bitable_crud.py
"""

from pten.fs_bitable import FsBitable, FsFieldType

if __name__ == "__main__":
    bitable = FsBitable()

    # 1. 创建多维表格（自带一张空数据表），返回的 url 可直接在浏览器打开
    app_res = bitable.create_app(name="pten示例表格")
    app = app_res["data"]["app"]
    app_token = app["app_token"]
    print(f"app_token: {app_token}")
    print(f"url: {app['url']}")

    # 2. 创建数据表并指定字段；type 用 FsFieldType 枚举（与裸数字等价，见 FsFieldType 注释）
    fields = [
        {"field_name": "姓名", "type": FsFieldType.TEXT},
        {"field_name": "年龄", "type": FsFieldType.NUMBER},
        {"field_name": "城市", "type": FsFieldType.SINGLE_SELECT},
    ]
    table_res = bitable.create_table(app_token, "示例数据表", fields=fields)
    table_id = table_res["data"]["table_id"]
    print(f"table_id: {table_id}")

    # (可选步骤,校验输入记录合法性) pre 3. 列出字段，并预校验待写入字段是否符合表定义
    # （未知字段 / 只读系统字段会在本地被拦截，避免打到服务端才暴露错误）
    print(bitable.list_fields(app_token, table_id))
    bitable.validate_record_fields(
        app_token, table_id, fields={"姓名": "张三", "年龄": 18, "城市": "深圳"}
    )

    # 3. 新增一条记录（fields 的键为字段名，值类型由字段类型决定，详见 create_record 注释）
    record_res = bitable.create_record(
        app_token,
        table_id,
        fields={"姓名": "张三", "年龄": 18, "城市": "深圳"},
    )
    record_id = record_res["data"]["record"]["record_id"]
    print(f"record_id: {record_id}")

    # 4. 增量更新记录（只更新传入的字段；置空传 None）
    print(bitable.update_record(app_token, table_id, record_id, fields={"年龄": 19}))

    # 5. 列出多维表格下的所有数据表（响应含分页 has_more / page_token）
    print(bitable.list_tables(app_token))

    # 6. 删除记录
    print(bitable.delete_record(app_token, table_id, record_id))

    # 7. 删除数据表（注意：多维表格只剩最后一张表时不允许删除）
    print(bitable.delete_table(app_token, table_id))
