# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在本仓库中处理代码时提供指引。

## 项目

`pten` 是一个调用飞书 API 和企业微信 API 的 Python 库（src-layout，`src/pten/`），覆盖机器人/应用消息、通讯录、文档、回调加解密，外加一小组「notice」提醒助手（生日提醒、天气、LLM 对话）。

## 常用命令

```bash
# 可编辑安装（拉取依赖：apscheduler、lunardate、openai、pycryptodome）
pip install -e .
# 测试依赖
pip install "pytest>=3" "pytest-mock>=3"

# 从仓库根目录跑全部测试（conftest.py 会把 src/ 加入 sys.path，无需安装）
pytest

# 跑单个测试 / 文件 / 按关键字筛选
pytest tests/test_keys.py
pytest tests/test_wwmessager.py::test_app_msg_sender
pytest tests/test_wwapi.py -k jsapi
```

测试默认从仓库根目录运行。`Keys` 按查找链解析配置文件（显式 `keys_filepath` → `PTEN_KEYS_FILE` 环境变量 → `./pten_keys.ini` → `~/.pten/pten_keys.ini`；前两级严格，后两级探测），token 缓存（`pten_token.json`）落在解析出的配置文件同目录，日志文件（`pten.log`）相对 CWD 解析。

### 真实 API 测试

大多数测试通过 `pytest-mock` 的 `mocker` fixture mock 掉 `requests.get`/`requests.post`，并使用 `pten_keys_example.ini`。少数测试（`test_*_real_key`、生日调度器测试、`wwcrypt` 的 `VerifyURL`/`DecryptMsg`）会打真实 API，由 `tests/conftest.py` 里的开关控制：

- `use_real_keys = True` —— 放开 `test_real_keys.py` 里的真实 API 测试（它们直接读真实的 `pten_keys.ini`；mock 测试无论开关如何都始终用 `pten_keys_example.ini`）。
- `enable_long_time_tests = True` —— 放开长耗时的 `BlockingScheduler` 生日测试。

## 架构

本节的人类可读图文详版见 `docs/architecture.md`；架构有变化时两边需同步更新。

### 配置与状态 —— `keys.py`
`Keys` 是其余所有模块唯一的配置依赖。它按查找链解析配置文件 —— 显式 `keys_filepath`（严格：文件缺失不回退）→ `PTEN_KEYS_FILE` 环境变量（严格）→ `./pten_keys.ini` → `~/.pten/pten_keys.ini`（后两级探测；两者都不存在时回落 `./pten_keys.ini`，保留旧的「初始化告警、get 时抛错」行为）—— 然后读取（`configparser`，节为 `ww` / `fs` / `globals` / `proxies` / `notice`，外加可选的 `[llm:<name>]` provider 节，由 `Keys.list_llm_providers()` 枚举；文件先按 UTF-8 读，失败回落本机编码以兼容老的 GBK 文件 —— `Keys._read_keys_file`），并持有 token/ticket 缓存：access token 和 corp/app jsapi ticket 持久化到 `pten_token.json`（与解析出的配置文件同目录，因此 `~/.pten` 配置的 token 不会散落到 CWD），键为 `ww_`/`fs_` + `sha1(凭证)`（WW 是 corpid+corpsecret，飞书是 app_id+app_secret），7200 秒过期；内存 access-token 缓存按同样方式键控，因此 WW 和飞书的 token 可共享一个 `Keys` 实例。`[fs]` 里可选的 `receive_id`/`receive_id_type`（`Keys.get_fs_receive_id*`）提供 `fs_messager.FsAppMsgSender` 的默认收件人。公开类接受 `keys_filepath=None`（触发查找链）加可选的 `keys: Keys`，以便跨模块注入共享的 `Keys` 实例（及其 token 缓存）。

### 共享底座 —— `base_api.py`
`base_api.AbstractApi` 持有企业微信与飞书共用的 HTTP 管道：`http_call` 分发（POST/GET/POST_FILE/DELETE/PUT —— DELETE 像 GET 一样把查询参数经 `_append_args` 拼进 URL；PUT 像 POST 一样把请求体放在 `args` 里）、URL 构造（`_make_url`、`_append_args`）、token 替换（`_append_token`）、厂商请求头（`_get_headers(url)` 钩子 —— 默认为空，飞书模块重写它以添加 `Content-Type`/`Authorization`；`_post_file` 会摘掉 `Content-Type`，让 requests 自行生成 multipart boundary）、响应检查（`_check_response` → 成功码不为 `0` 时抛 `ApiException`）以及 token 过期重试（最多 3 次）。模块级的 `make_token_key(prefix, *credentials)` 帮助函数构造两家厂商持久化的 `ww_`/`fs_` token 缓存键。各厂商模块继承它并设置类属性：`BASE_URL`；`RESPONSE_CODE_FIELD`/`RESPONSE_MSG_FIELD`（WW 是 `errcode`/`errmsg`，飞书是 `code`/`msg`）；`TOKEN_PLACEHOLDERS` —— 有序的 `(占位符, getter 名)` 元组，更长/更具体的占位符必须排前面（如 `SUITE_ACCESS_TOKEN` 在 `ACCESS_TOKEN` 之前，因为前者包含后者；`_append_token`/`_refresh_token` 取第一个匹配）；以及 `TOKEN_EXPIRED_CODES`（飞书 webhook 基类为空，刷新在那里是 no-op）。`_debug_url` 钩子让 WW 在 debug 模式追加 `&debug=1`。

### 企业微信 API 层 —— `wwapi.py`
`AbstractApi` 是 `base_api.AbstractApi` 的配置子类：`BASE_URL=https://qyapi.weixin.qq.com`、响应字段 `errcode`/`errmsg`、全部四个 token 占位符、`TOKEN_EXPIRED_CODES=(40014,42001,42007,42009)`。端点定义放在模块级字典（`BOT_API_TYPE`、`CORP_API_TYPE`、`SERVICE_CORP_API_TYPE`、`SERVICE_PROVIDER_API_TYPE`）里，逻辑名 → `[shortUrl, method]`。URL 带占位符（`ACCESS_TOKEN`、`WEBHOOK_KEY`、`SUITE_ACCESS_TOKEN`、`PROVIDER_ACCESS_TOKEN`），`_append_token` 调用子类的 `get_*` 方法惰性替换；token 过期 errcode 时 `_refresh_token` 调对应的 `refresh_*` 并最多重试 3 次。`errcode == 0` 之外 `_check_response` 抛 `ApiException(errcode, errmsg)`。子类：`BotApi`（仅 webhook）、`CorpApi`（access_token + jsapi ticket）、`ServiceCorpApi`、`ServiceProviderApi`。

### 飞书 API 层 —— `fs_api.py` / `fs_messager.py`
`FsAbstractApi` 是 `base_api.AbstractApi` 的配置子类：`BASE_URL=https://open.feishu.cn/open-apis`、响应字段 `code`/`msg`、仅 webhook（`WEBHOOK_KEY` 占位符）、`TOKEN_EXPIRED_CODES=()`（webhook 无需鉴权），并重写 `_get_headers` 加上飞书要求的 JSON `Content-Type`。`FsCorpApi` 负责自建应用：用 `[fs]` 里的 `app_id`/`app_secret`（或显式参数）从 `auth/v3/tenant_access_token/internal` 取 `tenant_access_token`，经 `Keys` 以 `fs_<sha1(app_id+app_secret)>` 为 token 键缓存；与企业微信的 URL 占位符不同，token 通过 `_get_headers` 以 `Authorization: Bearer` 请求头携带（token 端点本身跳过该请求头，这也切断了过期刷新的递归）。飞书的过期码（`99991661`/`99991663`）通过重写 `_refresh_token` 刷新并重试，因为 URL 里从不出现 token 占位符。带非 token 查询参数的端点携带占位符，由 sender 在调用前替换（如 `MESSAGE_SEND` 的 `receive_id_type=RECEIVE_ID_TYPE`，由 `FsAppMsgSender._send` 替换）。由于 HTTP 管道经 `base_api` 共享，扩展飞书支持现在与企业微信自动对齐 —— 往 `fs_api.BOT_API_TYPE`（webhook）或 `CORP_API_TYPE`（tenant token）加端点条目，再在 sender 上加薄方法；响应成功即 `code == 0`。`CORP_API_TYPE` 里的 `BITABLE_*` 条目（应用/数据表/记录的创建/列表/删除，记录更新）支撑 `fs_bitable.FsBitable`，它按调用替换路径占位符 `APP_TOKEN`/`TABLE_ID`/`RECORD_ID`（类似 `MESSAGE_SEND` 的 `RECEIVE_ID_TYPE`）；删除端点走 `base_api` 的 `DELETE` 分发，更新记录走 `PUT` 分发。

### 高层模块
- `wwmessager.py` —— `MsgSender` 基类；`BotMsgSender`（webhook，用 `Queue` 自限速每分钟 20 条）和 `AppMsgSender`（access_token，按有无 `chatid` 路由到 `appchat/send` 或 `message/send`，解析 `touser`/`toparty`/`totag`，缺省 `@all`）。媒体上传走 `_get_media_id`。
- `fs_messager.py` —— `FsMsgSender` 基类，飞书侧：`FsBotMsgSender`（webhook，文本/卡片）和 `FsAppMsgSender`（经 `FsCorpApi` 的自建应用；每次发送带 `receive_id` + `receive_id_type` —— open_id/user_id/union_id/email/chat_id —— 打到 `im/v1/messages`，`content` 按 im API 做 JSON 序列化；省略 `receive_id` 时回落 `[fs]` 配置的默认收件人（`receive_id` + 可选 `receive_id_type`，构造时读一次 —— 配置的 receive_id_type 仅在收件人来自配置时生效），两者都缺时不起请求、直接返回错误 dict）。
- `fs_bitable.py` —— `FsBitable` 封装 `FsCorpApi` 做多维表格 (Base) 操作：`create_app` / `create_table` / `list_tables` / `list_fields` / `create_record` / `update_record` / `delete_record` / `delete_table`，按调用替换路径占位符 `APP_TOKEN`/`TABLE_ID`/`RECORD_ID`；删除记录/删除表走 `DELETE` 分发，更新记录走 `base_api` 的 `PUT` 分发。`list_fields` 列出数据表字段（field_name/type/ui_type/property/is_primary 等）；`validate_record_fields` 拉取字段清单后在本地预检待写入字段（未知字段、只读/系统字段），opt-in 不侵入 `create_record`。
- `wwcontact.py` —— `Contact` 封装 `CorpApi`，用 `contact_sync_secret`（来自 `[ww]`，或显式传入）而非 `app_secret`。
- `wwdoc.py` —— `Doc` 封装 `CorpApi`，覆盖 wedoc / smartsheet / form 端点。
- `wwcrypt.py` —— `WXBizMsgCrypt`（VerifyURL / DecryptMsg / EncryptMsg）做回调消息加解密。Vendored 自 `weworkapi_python`。
- `notice.py` —— `Notice` 基类（默认 `report_func=print`）；`Birthday`（`lunardate` 农历 + 阳历，`apscheduler` 调度并自动排下一年，处理闰月）；`LLM`（通用 OpenAI 兼容 chat 客户端，接受 `base_url`/`api_key`/`model`；`provider="openai"` 时读 `[llm:openai]` 节（`base_url`/`api_key`/`model`），否则回落 `[notice]` 的 `llm_*`；显式参数始终优先于配置；取代 `Deepseek`）；`Deepseek`（仅 DeepSeek 的预设，OpenAI 客户端指向 DeepSeek base_url —— 已被 `LLM` 取代）；`Weather`（心知天气 seniverse API）。

### 日志
导入 `pten`（即各模块的 `from . import logger`）会执行 `src/pten/__init__.py`，配置一个具名 `logger`：彩色控制台 handler 加 30MB 滚动的 `pten.log` 文件 handler。包内代码用这个 `logger`，不用 `print`。

## 约定

- **新增 API 端点？** 往 `wwapi.py`（或 `fs_api.py`）相应的 `*_API_TYPE` 字典加一条，再在高层类（`Contact`、`Doc`、sender 等）上暴露一个薄方法：构建 `data` 字典并调 `self.api.http_call(...)`。保持邻方法的数据形状与文档链接注释风格。
- **接口变更时同步示例：** `examples/` 每个文件只演示一个模块的最常用用法，改公开接口后更新对应示例；示例不以 `test_` 开头（pytest 不收集）。
- **测试中的响应断言：** 企业微信 → `assert_ww_response`（检查 `errcode==0`、`errmsg=="ok"`）；飞书 → `assert_fs_response`（检查 `code==0`、`msg=="success"`）。两者都在 `tests/conftest.py`。
- **`pten_keys.ini` 与 `pten_token.json` 已 gitignore**（真实密钥/缓存 token）。`pten_keys_example.ini` 是提交进库的假凭证 fixture，mock 测试用它。
