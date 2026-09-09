# 用 pten 操作飞书多维表格：FsBitable 增删改查上手指南

`pten` v0.4.9 新增了 `FsBitable` 模块，把飞书多维表格（Base）的增删改查封装成几个直白的方法；v0.4.10 又补上了 `FsFieldType` 字段类型枚举。在这之前，pten 的飞书能力止步于"发消息"——webhook 机器人和自建应用消息；现在，脚本可以直接把数据写进多维表格，让飞书给你的自动化任务当一块"看得见的数据库"。

## 1. 为什么用代码操作多维表格

多维表格是飞书里的云端轻量数据库：表格的皮、数据库的骨。数据按三层组织——**多维表格（app）→ 数据表（table）→ 记录（record）**：一张多维表格里可以建多张数据表，每张表有自己的字段结构，每条记录就是一行数据。

适合交给代码维护的场景：

- **告警/事件跟踪**：监控脚本每触发一条告警，就往多维表格里写一行，再发张卡片消息给负责人——表格是台账，卡片是通知，一条链路；
- **定时任务产出登记**：天气播报、生日提醒这类 pten notice 模块跑的任务，跑完顺手记一笔；
- **CI/构建结果记录**：流水线跑完把版本号、耗时、结论写成一行，比翻日志快；
- **小团队的共享数据库**：不想申请数据库、又需要多人协作读写结构化数据时，多维表格是最省事的选择。

## 2. 准备工作（飞书侧）

`FsBitable` 与 `FsAppMsgSender` 一样，走自建应用的 `tenant_access_token` 鉴权，凭证同源——已经为[发应用消息](https://mp.weixin.qq.com/s/6ySmgTx0giDKcqHqXzWCrw)建过应用的话，直接复用即可：

1. 在[飞书开放平台](https://open.feishu.cn)创建一个**企业自建应用**；
2. 在"凭证与基础信息"页拿到 **App ID** 和 **App Secret**；
3. 开通多维表格权限：**`bitable:app`（查看、评论、编辑和管理多维表格）** 或 **`base:app:create`（创建多维表格）**，开启任一即可；
4. **发布一个版本**，权限才对租户生效；
5. **确保应用是目标多维表格的所有者或协作者**，否则调用会失败。要操作人工创建的多维表格，可通过"添加文档应用"的方式把应用加为协作者，详见[开通文档、电子表格等其它云文档资源权限](https://open.feishu.cn/document/faq/trouble-shooting/how-to-add-permissions-to-app#223459af)；或用 `create_app` 以应用身份创建一篇多维表格（应用天然是所有者），再用 `tenant_access_token` 调用后续接口。

两个细节：`create_app` 传 `folder_token` 指定归属文件夹时，应用需对该文件夹有编辑权限，缺省则创建在云空间根目录；应用能访问的多维表格也受应用可用范围约束。

## 3. 安装与配置

pten 主页：[GitHub](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)）。本功能自 v0.4.9 起发布，建议直接用 v0.4.11+（带 `FsFieldType` 与配置查找链）：

```bash
pip install -U pten  # >= 0.4.11，要求 Python 3.8+
```

也可以 clone 仓库后源码安装：`pip install -e .`。

凭证放在 `pten_keys.ini` 的 `[fs]` 段，多维表格只需要 `app_id`/`app_secret` 两个键：

```ini
[fs]
app_id=cli_slkdjalasdkjasd
app_secret=dskLLdkasdjlasdKK
; webhook_key 等其他键与 bitable 无关，按需保留
```


## 4. 基础使用：三层数据模型，七个方法

### 4.1 实例化与方法总览

```python
from pten.fs_bitable import FsBitable

bitable = FsBitable()  # 缺省按 传入路径/PTEN_KEYS_FILE/当前目录/~/.pten/ 顺序查找配置，也可传路径或 keys 实例
```

七个方法按"对象 × 动作"对齐三层数据模型：

| 方法 | 对象 | 动作 | 对应接口 |
|---|---|---|---|
| `create_app` | 多维表格 | 增 | [创建多维表格](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app/create) |
| `create_table` | 数据表 | 增 | [新增数据表](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/create) |
| `list_tables` | 数据表 | 查 | [列出数据表](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/list) |
| `delete_table` | 数据表 | 删 | [删除数据表](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/delete) |
| `create_record` | 记录 | 增 | [新增记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create) |
| `update_record` | 记录 | 改 | [更新记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/update) |
| `delete_record` | 记录 | 删 | [删除记录](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/delete) |

所有方法返回飞书原始响应 dict：成功即 `code == 0`、`msg == "success"`，业务数据在 `data` 里。

### 4.2 多维表格与数据表

```python
# 创建多维表格（自带一张空数据表），返回 data.app 含 app_token / default_table_id / url
resp = bitable.create_app(name="运维告警台账", time_zone="Asia/Shanghai")
app_token = resp["data"]["app"]["app_token"]
print(resp["data"]["app"]["url"])  # 浏览器里直接打开看一眼

# 新增一张数据表，fields 定义字段结构
resp = bitable.create_table(
    app_token=app_token,
    name="告警记录",
    fields=[
        {"field_name": "告警名", "type": 1},    # 文本；首字段须为索引字段
        {"field_name": "等级", "type": 3},       # 单选
        {"field_name": "发生时间", "type": 5},   # 日期
    ],
)
table_id = resp["data"]["table_id"]

# 列出多维表格下的所有数据表
resp = bitable.list_tables(app_token=app_token)
for table in resp["data"]["items"]:
    print(table["table_id"], table["name"])

# 删除数据表（多维表格里只剩最后一张表时不允许删）
bitable.delete_table(app_token=app_token, table_id=table_id)
```

`create_table` 的 `name` 限 1~100 字符、不可含 `/ \ ? * : [ ]`；`fields` 不传则创建仅含索引字段的空表。`list_tables` 支持分页：`page_size` 默认 20、最大 100，响应 `has_more` 为真时把返回的 `page_token` 传回去接着翻页。

### 4.3 记录的增、改、删

记录的 `fields` 参数是 `{字段名: 值}` 字典，值按字段类型填（完整对照见 5.2）：

```python
# 新增记录
resp = bitable.create_record(
    app_token=app_token,
    table_id=table_id,
    fields={"告警名": "prod-web CPU 高", "等级": "P1"},
)
record_id = resp["data"]["record"]["record_id"]

# 更新记录：增量更新，只动传入的字段；要把某字段置空就传 null
bitable.update_record(
    app_token=app_token,
    table_id=table_id,
    record_id=record_id,
    fields={"等级": "P2"},
)

# 删除记录
resp = bitable.delete_record(
    app_token=app_token, table_id=table_id, record_id=record_id
)
assert resp["data"]["deleted"] is True
```

### 4.4 跑一条完整链路

把四步串起来——建多维表格、建数据表、写记录、删记录，每步从上一步的返回里取 ID（这也正是 pten 用真实凭证跑的集成测试链路）：

```python
import time

ts = time.strftime("%Y%m%d%H%M%S")
resp = bitable.create_app(name=f"autotest_{ts}")
app_token = resp["data"]["app"]["app_token"]

resp = bitable.create_table(
    app_token=app_token, name="数据表",
    fields=[{"field_name": "名称", "type": 1}],
)
table_id = resp["data"]["table_id"]

resp = bitable.create_record(
    app_token=app_token, table_id=table_id, fields={"名称": f"record_{ts}"},
)
record_id = resp["data"]["record"]["record_id"]

resp = bitable.delete_record(
    app_token=app_token, table_id=table_id, record_id=record_id
)
```

链路里创建的多维表格不会被清理——pten 目前没封装"删除多维表格"（它属于云文档接口，超出 bitable 范围），建出的 app 需要事后人工清理，这也是链路里 app 名带时间戳的原因。

## 5. 进阶用法

### 5.1 FsFieldType：别再裸写魔法数字

v0.4.10 引入 `FsFieldType` 枚举，替代 `{"type": 1}` 里的裸数字——`IntEnum` 与裸数字完全等价（序列化后仍是数字），旧代码不用改，新代码更好读。常用取值：

| 枚举 | 值 | 枚举 | 值 |
|---|---|---|---|
| `TEXT` 多行文本 | 1 | `URL` 超链接 | 15 |
| `NUMBER` 数字 | 2 | `ATTACHMENT` 附件 | 17 |
| `SINGLE_SELECT` 单选 | 3 | `SINGLE_LINK` 单向关联 | 18 |
| `MULTI_SELECT` 多选 | 4 | `LOOKUP` 查找引用 | 19 |
| `DATETIME` 日期 | 5 | `FORMULA` 公式 | 20 |
| `CHECKBOX` 复选框 | 7 | `DUPLEX_LINK` 双向关联 | 21 |
| `USER` 人员 | 11 | `LOCATION` 地理位置 | 22 |
| `PHONE` 电话号码 | 13 | `GROUP_CHAT` 群组 | 23 |

另有 `WORKFLOW`（流程）和 `BUTTON`（按钮）两类只读字段（写接口不支持新增或编辑），以及 1001~1005 的系统字段（创建/修改时间、创建/修改人、自动编号）。字段细节见[官方字段类型指南](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-field/guide)。

```python
from pten.fs_bitable import FsBitable, FsFieldType

bitable.create_table(
    app_token=app_token,
    name="值班表",
    fields=[
        {"field_name": "姓名", "type": FsFieldType.TEXT},
        {"field_name": "生日", "type": FsFieldType.DATETIME,
         "property": {"date_formatter": "yyyy/MM/dd"}},
    ],
)
```

`create_table` 的首字段必须是索引字段，可选 `TEXT`/`NUMBER`/`DATETIME`/`PHONE`/`URL`/`FORMULA`/`LOCATION`；`property` 传字段属性（如日期格式）。

### 5.2 记录字段值怎么填

`create_record`/`update_record` 的 `fields` 值按字段类型对号入座：

| 字段类型 | 值写法 |
|---|---|
| 文本 / 单选 | `str`（单选传选项名） |
| 数字 | `10` |
| 多选 | `["选项A", "选项B"]` |
| 日期 | 毫秒时间戳 |
| 复选框 | `True` / `False` |
| 人员 | `[{"id": "ou_xxx"}]` |
| 超链接 | `{"text": "显示名", "link": "https://..."}` |
| 附件 | `[{"file_token": "..."}]` |
| 单/双向关联 | `[record_id, ...]` |
| 地理位置 | `"lng,lat"` |

### 5.3 实用参数

- `user_id_type`：人员字段里的 ID 类型（`open_id`/`union_id`/`user_id`），`create_record`/`update_record` 可选，缺省 `open_id`；
- `client_token`：`create_record` 的 uuidv4 幂等键——请求重试时传同一个值，服务端不会写入重复记录；
- `ignore_consistency_check`：写操作的一致性读写检查开关，特殊时序场景才需要动它；
- 共享 `Keys`：与其他模块共用一份配置和 token 缓存——

```python
from pten.keys import Keys
from pten.fs_bitable import FsBitable
from pten.fs_messager import FsAppMsgSender

keys = Keys("pten_keys.ini")
bitable = FsBitable(keys=keys)
app = FsAppMsgSender(keys=keys)  # 写完台账，顺手发条卡片通知
```

## 6. 常见问题与注意事项

- **权限没生效**：开了 `bitable:app` 但没发布应用版本，调用会被拒；
- **操作已有表格报无权限**：应用不是该多维表格的所有者或协作者——把应用加为协作者，或用 `create_app` 以应用身份创建（见第 2 节第 5 步）；
- **app_token / table_id / record_id 从哪来**：`app_token` 在 `create_app` 返回里，也可从多维表格 URL（形如 `https://xxx.feishu.cn/base/<app_token>`）取；`table_id` 从 `create_table` 返回或 `list_tables` 查；`record_id` 从 `create_record`/`update_record` 返回；
- **删不掉数据表**：多维表格只剩最后一张数据表时，删除接口会拒绝——留张空表，或人工删掉整个多维表格；
- **token 要自己管吗**：不用。`FsCorpApi` 自动取 `tenant_access_token`、以 `Authorization: Bearer` 请求头携带、持久化到 `pten_token.json`，命中过期码（`99991661`/`99991663`）时自动刷新并重试，最多 3 次；
- **怎么判断成功**：`resp["code"] == 0`（`msg == "success"`）；失败时 dict 里带飞书的错误码和消息，照着处理即可；
- **怎么"查记录"**：当前的"查"是 `list_tables`（查数据表）；按条件查询记录的接口尚未封装，需要的话照现有模式扩展——在 `fs_api.CORP_API_TYPE` 加端点、`FsBitable` 加薄方法即可。

## 7. 小结

- `FsBitable` 七个方法覆盖多维表格、数据表、记录三层的增删改查（v0.4.9），`FsFieldType` 补齐字段类型的可读性（v0.4.10）；鉴权与 token 管理完全复用 pten 既有的自建应用链路，配好 `[fs]` 的 `app_id`/`app_secret` 就能用；
- 和消息能力组合是它最顺手的玩法：定时任务跑完把结果写进多维表格，再给负责人发张卡片，台账与通知一条链路；
- 更多细节见 [pten 主页](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)）的 README 与源码 docstring——每个方法都附了对应的飞书官方文档链接。
