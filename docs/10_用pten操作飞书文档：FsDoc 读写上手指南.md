# 用 pten 操作飞书文档：FsDoc 读写上手指南

`pten` v0.4.20 新增了 `FsDoc` 模块，把飞书文档（docx）的常用读写封装成几个直白的方法：创建与获取文档、读取纯文本与块列表、把文本或 markdown 追加到文档末尾、删除末尾块。至此，pten 的飞书能力凑齐了三块拼图——消息触达（`FsAppMsgSender`）、结构化数据（`FsBitable`）、长文档沉淀（`FsDoc`）。

## 1. 为什么用代码写飞书文档

自动化脚本最常见的尴尬：数据有了、日志有了，但"给人看的版本"没有——最后要么往群里贴聊天记录，要么截图了事。适合交给 `FsDoc` 的场景：

- **LLM 输出归档**：`pten.notice.LLM` 生成的日报、周报、会议纪要，直接 `append_markdown` 落进文档——标题、列表、表格原样保留，比复制粘贴干净得多；
- **本地 markdown 搬家**：手写好的 md 报告一行代码搬进飞书开始协作，本地截图自动上传回填到图片块，不用一张张传；
- **任务产出留痕**：告警、发布记录这类流水写进多维表格做台账（`FsBitable`），阶段性总结写进文档给人读——一份给程序查，一份给人看；
- **报告的"追加—撤销"**：写入姿势统一为"往文档末尾补内容"；写错了 `delete_last_blocks` 撤掉刚追加的部分，重试即可。

三种产出对应三块拼图，各有各的去处：

| 产出 | 合适的去处 | pten 模块 |
|---|---|---|
| 即时触达（告警、通知） | 消息 | `FsAppMsgSender`（v0.4.7） |
| 结构化数据（台账、指标） | 多维表格 | `FsBitable`（v0.4.9） |
| 叙述性长文（报告、纪要） | 文档 | `FsDoc`（v0.4.20） |

一个设计取舍值得先说明：`FsDoc` 的写入面刻意做窄——只支持"末尾追加"和"末尾删除"，不做任意位置插入、不做块级编辑。自动化任务九成的写入就是"往后面补内容"，把 docx 块模型的复杂度收敛在这两个姿势后面，接口才能保持直白。

## 2. 准备工作（飞书侧）

`FsDoc` 与 `FsAppMsgSender`、`FsBitable` 同走自建应用的 `tenant_access_token` 鉴权，凭证同源——已经为发消息或多维表格建过应用的话，直接复用即可：

1. 在[飞书开放平台](https://open.feishu.cn)创建一个**企业自建应用**；
2. 在"凭证与基础信息"页拿到 **App ID** 和 **App Secret**；
3. 开通文档权限：**`docx:document`（查看、评论、编辑和管理云文档中所有文档）**——文档的创建与块读写靠它；`append_markdown` 的 convert 环节另需 **`docx:document.block:convert`**（文本内容转换为云文档块），带图片时素材上传另需 **`docs:document.media:upload`** 等任一上传权限；
4. **发布一个版本**，权限才对租户生效；
5. **确保应用是目标文档的所有者或协作者**：要操作人工创建的文档，可通过"添加文档应用"把应用加为协作者，详见[开通文档、电子表格等其它云文档资源权限](https://open.feishu.cn/document/faq/trouble-shooting/how-to-add-permissions-to-app#223459af)；或直接用 `create_document` 以应用身份创建（应用天然是所有者）。


## 3. 安装与配置

pten 主页：[GitHub](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)、[PyPI](https://pypi.org/project/pten/)）。本功能自 v0.4.20 起发布：

```bash
pip install -U pten  # >= 0.4.20（v0.4.18 起要求 Python 3.10+，更早版本 3.8+）
```

凭证放在 `pten_keys.ini` 的 `[fs]` 段，文档操作只需要 `app_id`/`app_secret` 两个键：

```ini
[fs]
app_id=cli_slkdjalasdkjasd
app_secret=dskLLdkasdjlasdKK
; webhook_key、receive_id 等其他键与文档操作无关，按需保留
```

## 4. 基础使用

### 4.1 实例化与方法总览

```python
from pten.fs_doc import FsDoc

doc = FsDoc()  # 缺省按 传入路径/PTEN_KEYS_FILE/当前目录/~/.pten/ 顺序查找配置，也可传路径或 keys 实例
```

各方法按"动作"对齐：

| 方法 | 动作 | 对应接口 |
|---|---|---|
| `create_document` | 增 | [创建文档](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create) |
| `append_text` | 增 | [创建块](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/create) |
| `append_markdown` / `append_markdown_from_file` | 增 | [markdown 转换](https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/document-docx/docx-v1/document/convert) + [创建嵌套块](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block-descendant/create) |
| `get_document` | 查 | [获取文档基本信息](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/get) |
| `get_raw_content` | 查 | [获取文档纯文本](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/raw_content) |
| `list_blocks` | 查 | [获取文档块列表](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/list) |
| `delete_last_blocks` | 删 | [删除块](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/batch_delete) |

所有方法返回飞书原始响应 dict：成功即 `code == 0`、`msg == "success"`，业务数据在 `data` 里。

### 4.2 创建文档与读取

```python
# 创建一篇空文档，title 纯文本、1-800 字符，缺省由服务端命名；
# folder_token 可指定归属文件夹（tenant_access_token 仅能指定应用自己创建的文件夹），
# 缺省创建在云空间根目录
resp = doc.create_document(title="运维周报")
document_id = resp["data"]["document"]["document_id"]
print(f"https://xxx.feishu.cn/docx/{document_id}")  # 拼出链接，浏览器里直接打开

# 文档基本信息：title / revision_id（随每次编辑递增）/ display_setting / cover
resp = doc.get_document(document_id)
print(resp["data"]["document"]["revision_id"])

# 纯文本：data.content，段落以 \n 分隔——喂给 LLM 做摘要正合适
content = doc.get_raw_content(document_id)["data"]["content"]

# 全部块：默认自动翻页聚合，data.items 为全量块
resp = doc.list_blocks(document_id)
for block in resp["data"]["items"]:
    print(block["block_id"], block["block_type"])
```

`create_document` 创建的是**空文档**，不支持带内容创建（要基于模板建文档得走 drive 的复制文件接口）；内容靠后面的 append 方法补。

块模型一句话就够用：文档根 page 块的 `block_id` 就是 `document_id`，它的 `children` 是**顶层块的有序列表**——`delete_last_blocks` 就是靠这个顺序定位末尾的。

### 4.3 追加一段文本

```python
# 一段纯文本作为一个文本块插到文档末尾；多行 \n 是软换行（同段落内换行）
resp = doc.append_text(document_id, "本周无重大故障\n值班按计划轮换")
print(resp["data"]["children"][0]["block_id"])  # 服务端生成的新块 ID

# 空白文本不发请求，直接返回本地错误 dict：{"code": -1, "msg": "待插入的文本不能为空"}
```

注意软换行的语义：`append_text` 里的 `\n` 是**同一段落内**的换行，不是分段。要让每行独立成段，用下一节的 `append_markdown`。

### 4.4 追加 markdown（推荐姿势）

```python
md = """## 本周概览

- 三个发布窗口全部按时完成
- 线上告警 12 条，闭环 11 条

| 服务 | 可用率 |
| --- | --- |
| web | 99.98% |
| api | 99.95% |
"""
resp = doc.append_markdown(document_id, md)
# resp 是最后一次「创建嵌套块」的响应：
# data.block_id_relations 为 convert 临时块 id → 真实 block_id 的映射
```

标题、有序/无序列表、表格、图片这些常用元素都会转成对应的块结构（完整支持范围以转换端点文档为准）。markdown 里的图片也不用操心：

```python
# 从文件读取后追加；图片自动下载/读取并上传回填到图片块，
# 相对路径图片按 md 文件所在目录解析；GBK 旧文件显式传 encoding
doc.append_markdown_from_file(document_id, "weekly_report.md")
doc.append_markdown_from_file(document_id, "legacy_report.md", encoding="gbk")
```

`![截图](shots/1.png)` 和 `![](https://example.com/a.png)` 都支持——本地图走文件、网络图走下载，三步回填全自动（细节见 5.2），单张失败只告警不中断。

### 4.5 删除末尾块：报告写错了怎么办

```python
# 删掉末尾 2 个顶层块（任意类型：文本/标题/表格/列表都行，连带其子树）
resp = doc.delete_last_blocks(document_id, count=2)
print(resp["data"]["document_revision_id"])  # 删除后的文档版本号

# 顶层块不足 count 时按现有数量全删；文档没有顶层块时不发请求，返回 None
```

粒度提醒：`count` 数的是**顶层块**——markdown 追加进来的一个表格、一个列表各算一个顶层块，所以 `delete_last_blocks(count=1)` 删的是"最后一个顶层元素"，不是最后一行。典型用法就是追加—撤销：写完读回来核对（`get_raw_content`），不对就撤掉刚追加的部分重来。

### 4.6 跑一条完整链路

```python
from pten.fs_doc import FsDoc

doc = FsDoc()

# 1. 创建文档（url 可拼为 https://<域名>/docx/<document_id>）
create_res = doc.create_document(title="pten示例文档")
document_id = create_res["data"]["document"]["document_id"]

# 2. 追加一段纯文本（一个文本块，\n 为软换行）
doc.append_text(document_id, "第一行\n第二行")

# 3. markdown 转换后追加到末尾（标题/列表/表格转成对应的块结构）
doc.append_markdown(document_id, "# 小节\n\n- 项目一\n- 项目二\n")

# 4. 读回纯文本（data.content，段落以 \n 分隔）
print(doc.get_raw_content(document_id)["data"]["content"])

# 5. 删除末尾 3 个顶层块（撤销刚才追加的内容，任意类型、连带子树）
doc.delete_last_blocks(document_id, count=3)

# 6. 文档基本信息（revision_id 随编辑递增）
print(doc.get_document(document_id)["data"]["document"])
```

完整可运行版本见 [examples/fs/doc_crud.py](../examples/fs/doc_crud.py)。注意示例会**真实创建文档**：结束时只删掉本例追加的块，文档本身保留，需要的话去云空间手动删。

## 5. 进阶用法

### 5.1 markdown 落进文档发生了什么

官方规定的两步：先调 convert 全局端点把 markdown 转成带**临时 block_id** 的块树（只转换、不修改任何文档）；再把块树作为子孙块对文档根块调「创建嵌套块」，插到末尾。`append_markdown` 把两步和善后全包掉了：

- **剥离只读字段**：Table 块的 `merge_info` 是服务端只读字段，插入前须剥离（官方要求），不剥服务端直接报错——pten 自动处理；
- **超限自动分批**：单次「创建嵌套块」的 `descendants` 与 `children_id` 各上限 1000——转换结果超限自动按**顶层子树**分批插入（保证每个顶层块的子树完整落在同一批里，顺序不乱），多批时返回最后一批的响应；
- **拿到真实块 ID**：返回值 `data.block_id_relations` 是"临时 id → 真实 block_id"的映射，需要继续操作具体块时从这里取。

### 5.2 图片的自动回填

convert 产出的图片块只是**占位**（token 为空），pten 在每批插入后按官方三步流程补齐：

1. **读取图片**：http(s) 按 URL 下载（走 `[proxies]` 的代理配置）；其余按本地路径读取，相对路径相对 `base_dir` 解析——`append_markdown` 缺省 CWD，`append_markdown_from_file` 自动传 md 文件所在目录；
2. **上传素材**：以图片块 ID 为 `parent_node` 调 drive 的 [上传素材](https://open.feishu.cn/document/server-docs/docs/drive-v1/media/upload_all)（`parent_type=docx_image`）；
3. **回写**：PATCH `replace_image` 把素材 token 填进图片块——不传宽高，服务端自动探测图片实际尺寸。

单张图片失败只记 warning、不中断整次追加（占位块保留，文档里会看到一个空图片块，可事后人工替换）。所以 `append_markdown_from_file` 场景最省心：md 和图片放同一个目录，整目录搬进飞书。

### 5.3 块列表的翻页控制

`list_blocks` 默认 `fetch_all=True`：自动翻页、聚合全部块后返回（`data.items` 为全量、`data.has_more=False`），缺省 `page_size=500`（API 上限，最小化请求次数）。要自己控制翻页传 `fetch_all=False`：拿到单页原始响应（含 `has_more`/`page_token`），把 `page_token` 传回去接着查——与 `FsBitable` 各列表接口的翻页约定完全一致。另有 `document_revision_id` 参数可钉住某个版本读（缺省 -1 即最新版）。

### 5.4 组合拳：LLM 生成周报，写文档、发通知

`FsDoc` 的设计动机就在这：LLM 的产出天然是 markdown，而飞书文档恰好是 markdown 最合适的"发布位"。三个模块共享一份 `Keys`（一份配置、一份 token 缓存）：

```python
from pten.keys import Keys
from pten.notice import LLM
from pten.fs_doc import FsDoc
from pten.fs_messager import FsAppMsgSender

keys = Keys("pten_keys.ini")              # 一份配置、一份 token 缓存
doc = FsDoc(keys=keys)                    # 写文档
app = FsAppMsgSender(keys=keys)           # 发通知
llm = LLM(keys_filepath="pten_keys.ini")  # LLM 读 [notice] 的 llm_*（或 [llm:<name>] 段）

# 让 LLM 把本周日志总结成 markdown 周报，落进文档，再发张卡片通知大家
summary = llm.get_completion(
    "把下面的运维日志总结成一份 markdown 周报，含概览、指标表格与遗留问题：\n" + logs
)
doc.append_markdown(document_id, summary)
app.send_card("周报已生成", "本周运维周报已写入文档，请查收")
```

反方向也通：`get_raw_content` 把既有文档读成纯文本，喂给 LLM 做摘要、翻译，再把结果追加回文档末尾。

## 6. 常见问题与注意事项

- **权限没生效**：开了 `docx:document` 但没发布应用版本，调用会被拒；
- **操作已有文档报无权限**：应用不是该文档的所有者或协作者——把应用加为协作者，或用 `create_document` 自建（见第 2 节第 5 步）；
- **document_id 从哪来**：`create_document` 返回里取；或从云空间文档 URL 取（形如 `https://xxx.feishu.cn/docx/<document_id>`，27 字符）；
- **`append_text` 和 `append_markdown` 怎么选**：纯文本一段话用前者（记住 `\n` 是软换行）；带结构的（标题/列表/表格/图片）或要每行独立成段，用后者；
- **表格块能改行列吗**：不能。表格作为块整体追加、整体删除都行，但行列的增删要走「更新块」接口，本封装未覆盖；
- **删错了能恢复吗**：`delete_last_blocks` 是真实删除，代码侧没有恢复接口——飞书文档自带版本历史可以人工找回，但更稳的做法是小批量写、写完 `get_raw_content` 核对再继续；
- **token 要自己管吗**：不用。`FsCorpApi` 自动取 `tenant_access_token`、以 `Authorization: Bearer` 请求头携带、持久化到 `pten_token.json`，命中过期码（`99991661`/`99991663`）时自动刷新并重试，最多 3 次；
- **怎么判断成功**：`resp["code"] == 0`（`msg == "success"`）；`append_text`/`append_markdown` 传空内容时不发请求，返回 `{"code": -1, "msg": ...}` 的本地错误 dict，按失败处理即可。

## 7. 小结

- `FsDoc` 覆盖文档的创建/读取、文本与 markdown 的末尾追加、末尾块删除；写入面刻意做窄（只追加、只删末尾），换来的是最直白的接口。鉴权与 token 管理完全复用 pten 既有的自建应用链路，配好 `[fs]` 的 `app_id`/`app_secret` 就能用；
- 和消息、多维表格组合是它最顺手的玩法：LLM/定时任务产出 markdown → `append_markdown` 落文档 → `send_card` 通知负责人，一条链路搞定；
- 更多细节见 [pten 主页](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)）的 README 与源码 docstring——每个方法都附了对应的飞书官方文档链接。
