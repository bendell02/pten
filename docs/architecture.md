# pten 代码架构

本文面向想读懂 pten 源码、或准备给它贡献代码的开发者，回答三个问题：**代码放在哪**（目录结构）、**怎么分层**（架构设计）、**一次调用怎么走完**（HTTP 生命周期）。各功能的用法教程见 docs/，可直接运行的最小示例见 `examples/`，本文只讲代码本身。

## 1. 总览

pten 是一个调用飞书开放平台、企业微信 API 的 Python 库（src-layout，`src/pten/`）。核心设计一句话：**两个厂商的 API 客户端共享同一个 HTTP 底座（`base_api`），厂商差异全部收敛为「配置子类」**——接入一个新厂商，只需要继承共享底座、设置几个类属性（基础 URL、响应字段名、token 占位符、过期错误码）并维护一张端点字典，不用碰任何 HTTP 逻辑。

三条设计原则贯穿整个代码库：

- **配置只有一份**：所有模块的配置读取都经过 `keys.py` 的 `Keys`，配置文件按「显式路径 → 环境变量 → 当前目录 → 用户主目录」查找链解析（详见 [docs 06](06_pten配置文件查找顺序：环境变量、当前目录、用户主目录.md)）
- **厂商差异收敛为配置**：HTTP 拼装、token 替换、响应检查、过期重试写在底座一处；厂商子类只声明「我不一样在哪」
- **高层封装很薄**：一个端点 = 端点字典里一行 + 高层类里一个薄方法，没有藏起来的逻辑

## 2. 目录结构

```
pten/
├── src/pten/              # 包源码（src-layout）
│   ├── __init__.py        # import 即初始化 logger（彩色控制台 + 滚动文件）
│   ├── keys.py            # 配置与状态：配置文件解析 + token/ticket 缓存
│   ├── base_api.py        # 共享 HTTP 底座
│   ├── wwapi.py           # 企业微信适配层（端点字典 + 4 个子类）
│   ├── fs_api.py          # 飞书适配层（端点字典 + 2 个子类）
│   ├── wwmessager.py      # 企业微信消息发送
│   ├── fs_messager.py     # 飞书消息发送
│   ├── wwcontact.py       # 企业微信通讯录
│   ├── wwdoc.py           # 企业微信智能文档 / 表格 / 收集表
│   ├── fs_bitable.py      # 飞书多维表格
│   ├── notice.py          # 提醒助手（生日 / 天气 / LLM）
│   └── wwcrypt.py         # 回调消息加解密（vendored）
├── tests/                 # pytest 测试（conftest.py 会把 src/ 加入 sys.path）
├── docs/                  # 教程与架构文档
├── examples/              # 最小可运行示例（ww / fs / notice 分组，真实调用 API）
├── pten_keys_example.ini  # 假凭证配置示例（提交进库，mock 测试用）
├── pten_keys.ini          # 本地真实配置（gitignore）
├── pten_token.json        # token 缓存（运行时生成，gitignore；跟随配置文件目录）
├── pten.log               # 日志（运行时生成，gitignore；相对 CWD）
└── setup.py / README.md / README.en.md / ReleaseNote.md / CLAUDE.md
```

## 3. 分层架构

```
高层封装层    用户直接使用的类，组合下层的 API 客户端
  · wwmessager.py   MsgSender / BotMsgSender / AppMsgSender
  · fs_messager.py  FsMsgSender / FsBotMsgSender / FsAppMsgSender
  · wwcontact.py    Contact
  · wwdoc.py        Doc
  · fs_bitable.py   FsBitable / FsFieldType
        │  组合：高层持有一个厂商 API 客户端实例
        ▼
厂商适配层    只提供「配置」：继承共享底座，设类属性 + 维护端点字典
  · wwapi.py   BotApi / CorpApi / ServiceCorpApi / ServiceProviderApi
  · fs_api.py  FsBotApi / FsCorpApi
        │  继承：厂商子类 extends base_api.AbstractApi
        ▼
共享底座    base_api.AbstractApi
  http_call 分发 / URL 构造 / token 替换 / 响应检查 / 过期重试
        │  组合：底座持有一个 Keys 实例
        ▼
配置与状态    keys.Keys
  配置文件查找链 + token/ticket 双层缓存

独立模块（不在分层栈上，仅依赖 keys 或无依赖）
  · notice.py     Notice / Birthday / LLM / Deepseek / Weather
  · wwcrypt.py    WXBizMsgCrypt（回调加解密，vendored 自 weworkapi_python）
  · __init__.py   logger 初始化（import pten 即触发）
```

依赖规则：**只允许上层依赖下层，同层模块互不依赖**（`wwmessager` 与 `fs_messager` 之间没有 import）。这条规则保证了「加一个新厂商」不会碰到任何旧厂商的代码。

## 4. 各层详解

### 4.1 配置与状态层 — `keys.py`

`Keys` 是所有其他模块唯一的配置依赖，负责三件事：

- **定位并读取配置文件**：查找链（显式路径 → `PTEN_KEYS_FILE` → `./pten_keys.ini` → `~/.pten/pten_keys.ini`，前两级严格、后两级探测）由 `_resolve_keys_filepath` 实现；文件按 UTF-8 读，失败回落本机编码以兼容老的 GBK 文件。节（section）包括 `ww` / `fs` / `globals` / `proxies` / `notice`，以及任意多个 `[llm:<name>]` provider 节（`list_llm_providers` 枚举）
- **提供类型化读取**：`get_key` / `get_keys` / `get_debug_mode` / `get_log_path` / `get_proxies` / `get_bot_weebhook_key` / `get_contact_sync_secret` / `get_fs_receive_id*` 等
- **持有 token/ticket 缓存**（详见第 6 节）：内存字典 + `pten_token.json` 持久化，两者都跟随最终解析出的配置文件所在目录

所有公开类都接受 `keys_filepath=None`（触发查找链）和一个可选的 `keys: Keys`——注入同一个 `Keys` 实例即可让企业微信和飞书模块**共享一份 token 缓存**。

### 4.2 共享底座 — `base_api.py`

`AbstractApi` 是企业微信、飞书两条线共用的 HTTP 管道，一个方法串起所有请求：`http_call(urlType, args)`。它负责：

- **分发**：按端点的 method 字段路由到 `POST` / `GET` / `POST_FILE` / `DELETE` / `PUT` 五种执行路径——GET 和 DELETE 把 `args` 拼成 query string（`_append_args`），POST 和 PUT 把 `args` 作为 JSON 请求体，POST_FILE 走 multipart 上传（`_post_file` 会摘掉 `Content-Type`，让 requests 自动生成 boundary）
- **URL 构造**：`_make_url` = `BASE_URL` + shortUrl
- **token 惰性替换**：`_append_token` 按 `TOKEN_PLACEHOLDERS` 声明的顺序找第一个命中的占位符，调对应 getter 替换进 URL
- **厂商请求头钩子**：`_get_headers(url)` 默认返回空 dict，由厂商子类按需重写（飞书在这里注入 `Authorization: Bearer`）
- **响应检查**：`_check_response` 读 `RESPONSE_CODE_FIELD` / `RESPONSE_MSG_FIELD`，非 0 抛 `ApiException(errCode, errMsg)`
- **过期重试**：响应码落在 `TOKEN_EXPIRED_CODES` 里时，`_refresh_token` 调对应的 `refresh_*` 后重试，整个调用最多 3 轮

模块级还有两个公共件：`ApiException`（唯一的异常类型）和 `make_token_key(prefix, *credentials)`（token 缓存键，见第 6 节）。

### 4.3 厂商适配层 — `wwapi.py` / `fs_api.py`

两个模块结构对称：一个配置基类（继承 `base_api.AbstractApi`）+ 若干端点字典 + 若干具体子类。端点字典把逻辑名映射为 `[shortUrl, method]`，URL 里带占位符（`ACCESS_TOKEN`、`WEBHOOK_KEY`、`APP_TOKEN`……），由底座或调用方替换。

两家厂商的配置差异一览：

| 类属性 / 钩子 | 企业微信 `wwapi` | 飞书 `fs_api` |
|---|---|---|
| `BASE_URL` | `https://qyapi.weixin.qq.com` | `https://open.feishu.cn/open-apis` |
| `RESPONSE_CODE_FIELD` / `MSG_FIELD` | `errcode` / `errmsg` | `code` / `msg` |
| token 携带方式 | URL 占位符（`ACCESS_TOKEN` 等） | 请求头 `Authorization: Bearer`（`FsCorpApi._get_headers`） |
| `TOKEN_PLACEHOLDERS` | `SUITE_ACCESS_TOKEN`、`PROVIDER_ACCESS_TOKEN`、`ACCESS_TOKEN`、`WEBHOOK_KEY` | webhook 基类仅 `WEBHOOK_KEY`；`FsCorpApi` 为空 |
| `TOKEN_EXPIRED_CODES` | 40014, 42001, 42007, 42009 | `FsCorpApi`：99991661, 99991663；webhook 基类为空 |
| `_get_headers` | 默认空 | JSON `Content-Type`（`FsCorpApi` 再加 Bearer） |
| `_debug_url` | 追加 `&debug=1` | 默认无 |

三个值得注意的细节：

- **占位符顺序有意义**：`TOKEN_PLACEHOLDERS` 是有序元组，更长的占位符必须排在它包含的子串之前（`SUITE_ACCESS_TOKEN` 在 `ACCESS_TOKEN` 之前），`_append_token` / `_refresh_token` 取第一个命中项
- **飞书 token 不走 URL 占位符**：`FsCorpApi` 从 `auth/v3/tenant_access_token/internal` 取 token 后经请求头携带，因此它重写 `_get_headers`（对 token 端点本身跳过鉴权头，避免递归）、并重写 `_refresh_token` 为「直接刷新」（底座按 URL 占位符定位刷新方法的方式对它不适用）
- **端点字典按凭据分档**：`wwapi` 有四张字典对应四种凭据（webhook key / access_token / suite token / provider token），子类各自挑用

### 4.4 高层封装层

用户直接打交道的一层，每个类组合一个厂商 API 客户端，方法大多是「构建 `data` 字典 → `self.api.http_call(...)`」：

| 模块 | 类 | 职责要点 |
|---|---|---|
| `fs_messager.py` | `FsMsgSender` / `FsBotMsgSender` / `FsAppMsgSender` | webhook 文本/卡片；自建应用按 `receive_id` + `receive_id_type`（open_id/user_id/union_id/email/chat_id）发 `im/v1/messages`，`content` 按 im API 序列化为 JSON；省略 `receive_id` 时回退 `[fs]` 配置的默认收件人 |
| `fs_bitable.py` | `FsBitable` / `FsFieldType` | 多维表格应用/数据表/记录的增删改查、列出字段（`list_fields`）；`FsFieldType` 是字段类型枚举（`IntEnum`，与裸数字等价）；路径占位符由 `_sub` 替换；`validate_record_fields` 拉取字段清单后本地预检未知字段与只读/系统字段 |
| `wwmessager.py` | `MsgSender` / `BotMsgSender` / `AppMsgSender` | 机器人 webhook 发送（`Queue` 自限速每分钟 20 条）；应用消息按有无 `chatid` 走 `appchat/send`（群）或 `message/send`（`touser`/`toparty`/`totag` 缺省 `@all`）；媒体上传经 `_get_media_id` |
| `wwcontact.py` | `Contact` | 通讯录（用户/部门/标签），用 `[ww] contact_sync_secret` 而非 `app_secret` 建 `CorpApi` |
| `wwdoc.py` | `Doc` | 智能文档 / 表格 / 收集表端点 |

两类占位符的分工在这里体现得最清楚（以飞书为例）：**token 类**（`WEBHOOK_KEY`，以及 WW 的 `ACCESS_TOKEN` 等）由底座自动替换；**路径/参数类**（`MESSAGE_SEND` 的 `RECEIVE_ID_TYPE` 由 `_send` 替换、多维表格的 `APP_TOKEN`/`TABLE_ID`/`RECORD_ID` 由 `_sub` 替换）由高层调用方在 `http_call` 之前替换成实参。

### 4.5 独立模块

- `notice.py` —— 不碰厂商 API 的提醒助手：`Notice`（基类，`report_func` 缺省 `print`，把通知抽象成「条件满足则上报」）；`Birthday`（`lunardate` 农历 + 阳历生日，`apscheduler` 调度、跨年自动排下一轮、处理闰月）；`LLM`（OpenAI 兼容 chat 客户端，`[llm:<name>]` 节或 `[notice] llm_*` 取配置，显式参数最高）；`Deepseek`（DeepSeek 预设，已被 `LLM` 取代）；`Weather`（心知天气 API）
- `wwcrypt.py` —— 回调消息加解密 `WXBizMsgCrypt`（`VerifyURL` / `DecryptMsg` / `EncryptMsg`），vendored 自 [weworkapi_python](https://github.com/sbzhu/weworkapi_python)，几乎零内部依赖
- `__init__.py` —— 包入口：`import pten` 即触发 `setup_logging()`，初始化全包共用的 `logger`（详见第 8 节）

## 5. 一次 HTTP 调用的生命周期

以 `FsAppMsgSender().send_text("hello")`（飞书自建应用发文本）为例：

```
send_text("hello")
  ├─ 构造 content = {"text": "hello"}
  └─ _send(msg_type:"text", content, receive_id, receive_id_type)
       ├─ content 按 im API 序列化为 JSON 字符串
       ├─ 替换参数占位符：MESSAGE_SEND 的 RECEIVE_ID_TYPE → 实际类型（open_id/chat_id…）
       │    （路径/参数类占位符由高层 sender 在进 http_call 前替换好）
       └─ http_call(["im/v1/messages?receive_id_type=open_id", "POST"], data)
            # CORP_API_TYPE["MESSAGE_SEND"]

            ─── 1–7 构成一次尝试，整体包在最多 3 轮的重试循环里 ───
            1. 分发：POST → _http_post（GET/DELETE 把参数拼进 URL；POST_FILE 走 multipart）
            2. _make_url：BASE_URL + shortUrl
            3. _append_token：按 TOKEN_PLACEHOLDERS 找命中占位符，调 getter 替换进 URL
                 · 飞书 TOKEN_PLACEHOLDERS 为空 → 本步 no-op
                 · （企业微信在此步把 ACCESS_TOKEN 换进 URL）
            4. _get_headers：飞书注入 Authorization: Bearer <tenant_access_token>
                 · get_access_token() → Keys 缓存命中直接用；miss 则 refresh 发真请求换取
                 · （企业微信 token 已在 URL，本步返回空 dict）
            5. DEBUG_MODE：logger.debug 打印完整 URL（WW 还会 _debug_url 加 &debug=1）
            6. requests.post(...)（proxies 支持 [proxies] 配置）
            7. 过期？code ∈ TOKEN_EXPIRED_CODES(99991661/99991663) → _refresh_token 后回到 1.
                 · 飞书重写 _refresh_token 为直接 refresh_access_token
                   （URL 里没有 token 占位符，底座按占位符定位的方式不适用）
            ─── 循环结束 ───
            8. _check_response：code == 0 → 返回整个响应 dict；否则抛 ApiException
```

图中 `·` 行是飞书相对底座通用做法的差异点。把飞书换成企业微信时：3. 把 `ACCESS_TOKEN` 替换进 URL、4. 返回空 dict、7. 走底座未重写的 `_refresh_token`（按占位符定位 `refresh_*`）；高层 sender 也不用预先替换 `RECEIVE_ID_TYPE` 这类占位符。两条路径共用 1./2./5./6./8. 全部底座步骤。

## 6. token 缓存机制

token（以及 jsapi ticket）的存取只发生在 `Keys` 里，API 子类通过 getter/refresh 三段式配合：

- **键**：`make_token_key(prefix, *credentials)` = `ww_` / `fs_` 前缀 + `sha1(凭证依次拼接)`。企业微信凭证是 `corpid + corpsecret`，飞书是 `app_id + app_secret`——键稳定，且明文凭证不会出现在缓存文件里
- **双层缓存**：内存字典（同一个 `Keys` 实例生命周期内）+ `pten_token.json`（跨进程持久化）。两份都落在最终解析出的配置文件同目录，`~/.pten/pten_keys.ini` 的全局配置不会把 token 散落到各个运行目录
- **过期**：7200 秒（飞书用 token 响应里的 `expire` 字段，缺省同为 7200）；内存与文件缓存带时间戳，`get_access_token` 先验过期再返回
- **三段式**：`get_*`（查缓存）→ miss 时 `refresh_*`（真发请求）→ `Keys.save_*`（写回双层缓存）。底座的过期重试调的就是 `refresh_*`
- jsapi ticket（`get_corp_jsapi_ticket` / `get_app_jsapi_ticket`）走同一套机制，仅在 WW `CorpApi` 上有

## 7. 如何新增一个 API 端点

以「飞书多维表格查询单条记录」为例，三步：

**第一步**：往 `fs_api.py` 的 `CORP_API_TYPE` 加一行（GET 端点，路径参数用占位符占位）：

```python
"BITABLE_RECORD_GET": [
    "bitable/v1/apps/APP_TOKEN/tables/TABLE_ID/records/RECORD_ID",
    "GET",
],
```

**第二步**：在 `fs_bitable.py` 加一个薄方法，替换路径占位符后走 `http_call`：

```python
def get_record(self, app_token, table_id, record_id, **kwargs):
    url = self._sub(
        CORP_API_TYPE["BITABLE_RECORD_GET"][0],
        APP_TOKEN=app_token, TABLE_ID=table_id, RECORD_ID=record_id,
    )
    return self.api.http_call([url, "GET"], kwargs)
```

**第三步**：加测试。mock `requests.get`，响应断言用 `assert_fs_response`（见第 8 节）。

企业微信侧完全同理，只是字典换成 `wwapi` 的四张之一、占位符换成 `ACCESS_TOKEN`（token 替换是自动的，薄方法里不用管）。新方法的注释风格请对齐邻方法：`:param` / `:return` 各一行，末尾附官方文档链接。

## 8. 测试与日志

### 测试

`tests/` 与源码模块一一对应，`conftest.py` 把 `src/` 加进 `sys.path`（不用装包就能跑），从仓库根目录 `pytest` 即可。两类测试：

- **mock 测试**（绝大多数）：`pytest-mock` 的 `mocker` 拦截 `requests.get` / `requests.post`，配置一律用 `pten_keys_example.ini` 的假凭证。响应断言有现成 helper——企业微信用 `assert_ww_response`（`errcode==0` 且 `errmsg=="ok"`），飞书用 `assert_fs_response`（`code==0` 且 `msg=="success"`）
- **真实 API 测试**：由 `tests/conftest.py` 里的两个开关控制，默认关闭——`use_real_keys` 打开 `test_real_keys.py` 的真实配置测试；`enable_long_time_tests` 打开生日调度器长跑测试（`BlockingScheduler`）

### 日志

`import pten` 即触发 `__init__.py` 的 `setup_logging()`：彩色控制台 handler + 30MB 滚动文件 handler（`pten.log`，相对 CWD，`delay=True` 到首次写入才建文件）。包内代码统一 `from . import logger` 后使用，不用 `print`。日志路径可通过 `setup_logging(log_path)` 更改，初始化失败时回退默认路径，保证 import 永不失败。

## 9. 与 CLAUDE.md 的关系

`CLAUDE.md` 的架构一节是本文的指令式摘要，供 Claude Code 使用；架构有变化时两边需要同步更新。
