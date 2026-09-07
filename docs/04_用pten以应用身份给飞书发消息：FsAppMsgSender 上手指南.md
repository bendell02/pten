# 用 pten 以应用身份给飞书发消息：FsAppMsgSender 上手指南

`pten` v0.4.7（commit `36c702d`）新增了一个实用功能：**飞书自建应用以 tenant 身份发消息**。在这之前，pten 的飞书消息只能走 webhook 机器人——消息被固定钉死在机器人所在的那个群里；而现在，你可以把消息发给**租户内的任意用户或任意群**，文本和卡片都支持。

## 1. 为什么需要自建应用

webhook 机器人（`FsBotMsgSender`）用起来很简单，往群里加个机器人、拿到一个 webhook key 就能发消息。但它有三个硬伤：

1. **只能发到机器人所在的群**——没法给某个具体的人发单聊消息；
2. **限流 20 条/分钟**，脚本里内建了睡眠等待；
3. 一个 webhook 只对应一个群，多个群就要配多个 webhook。

自建应用（`FsAppMsgSender`）走的是飞书的 [im/v1/messages](https://open.feishu.cn/document/server-docs/im-v1/message/create) 接口，以应用身份调用，接收者由参数指定，上面三个问题都不存在了：

| | `FsBotMsgSender`（webhook） | `FsAppMsgSender`（自建应用） |
|---|---|---|
| 配置 | `webhook_key` | `app_id` + `app_secret` |
| 鉴权 | 无 | `tenant_access_token`（自动管理） |
| 接收者 | 机器人所在群 | 任意用户 / 任意群 |
| 限流 | 20 条/分钟 | 不受 webhook 限流约束 |
| 消息类型 | 文本、卡片 | 文本、卡片 |

## 2. 准备工作（飞书侧）

1. 在[飞书开放平台](https://open.feishu.cn)创建一个**企业自建应用**；
2. 在"凭证与基础信息"页拿到 **App ID** 和 **App Secret**；
3. 给应用开通消息权限（`im:message`，即"获取与发送单聊、群组消息"）；
4. **发布一个版本**，权限才对租户生效；
5. 注意应用的**可用范围**：接收者必须在这个范围内，否则发消息会报错。

接收者的 ID 从哪来？`open_id` 可以通过飞书通讯录接口获取，`chat_id`（群的 ID）可以通过"获取用户或机器人所在群列表"之类的接口拿到。调试阶段也可以用 [API 调试台](https://open.feishu.cn/api-explorer)快速查。

## 3. 安装与配置

功能随 v0.4.7 发布，直接升级即可：

```bash
pip install -U pten  # >= 0.4.7
```

凭证放在 `pten_keys.ini` 里。`[fs]` 段在原有的 `webhook_key` 之外，新增了四个键：

```ini
[fs]
webhook_key=cb46342e-4ecb-436c-b91d-6abcabc8c033e
app_id=cli_slkdjalasdkjasd
app_secret=dskLLdkasdjlasdKK
; AppMsgSender 的默认消息接收者（可选）：未显式传 receive_id 的发送会发给它
receive_id=ou_84a7b7e2d5219af3c6b0e4d8a2f1c5d6
; 默认接收者的 ID 类型，缺省 open_id，可选 user_id/union_id/email/chat_id
;receive_id_type=open_id
```

`app_id`/`app_secret` 是必填的；`receive_id`/`receive_id_type` 是可选的"默认接收者"——配置之后，调用发消息方法时可以不传接收者，消息会发给它。适合"我就是想给固定的某个人/某个群发通知"这类最常见的场景。

> 提示：`pten_keys.ini`、token 缓存 `pten_token.json` 都是相对**当前工作目录**解析的，建议在固定目录（如仓库根目录）下运行你的脚本。

## 4. 三行代码发消息

```python
from pten.fs_messager import FsAppMsgSender

app = FsAppMsgSender()  # 缺省读当前目录的 pten_keys.ini，也可传路径
response = app.send_text("hello world from app")
```

返回值是个 dict，成功时 `code == 0`、`msg == "success"`；失败时带着飞书返回的错误码和消息，可以据此处理：

```python
response = app.send_text("hello world from app")
if response.get("code") != 0:
    print(f"发送失败: {response}")
```

不传 `receive_id` 时用的是配置文件里的默认接收者。要发给别的人或群，显式指定即可——`receive_id` 配上 `receive_id_type`（缺省 `open_id`），五种取值覆盖了单聊和群聊：

```python
# 按 open_id 发给某个用户（缺省类型）
app.send_text("你好", receive_id="ou_xxxx")

# 直接按邮箱发——给同事发消息最省事的方式
app.send_text("你好", receive_id="ben@example.com", receive_id_type="email")

# 发到群（chat_id）
app.send_text("群消息", receive_id="oc_xxxx", receive_id_type="chat_id")

# 其他可用类型：user_id / union_id
```

## 5. 发卡片

通知类消息用卡片更醒目。`send_card` 构造一张带标题和正文的简单卡片，正文支持 lark_md 语法：

```python
app.send_card("部署通知", "服务 **web-1** 已上线 ✅", template="green")

# 告警场景换个配色，再指定一个群
app.send_card(
    "CPU 告警",
    "主机 **prod-web** CPU 使用率 **92%**，请及时处理",
    template="red",
    receive_id="oc_xxxx",
    receive_id_type="chat_id",
)
```

`template` 控制卡片头部的配色，可选 `blue`（默认）/ `red` / `orange` / `yellow` / `green` / `indigo` / `grey` 等。更复杂的卡片结构可以参考[飞书卡片 JSON 结构文档](https://open.feishu.cn/document/feishu-cards/card-json-v2-structure)。

两个小限制：文本消息最长 150 字符；卡片要求标题和正文都非空，否则不会发起请求，直接返回本地错误 dict。

## 6. token 管理：你不用管的那部分

自建应用调接口需要 `tenant_access_token`，这通常是接入飞书 API 最繁琐的一环。`FsAppMsgSender` 背后的 `FsCorpApi` 把它整个接管了：

1. **获取**：首次调用时用 `app_id`/`app_secret` 从[凭证接口](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal)换 token；
2. **携带**：和企业微信把 token 拼在 URL 里不同，飞书走的是 `Authorization: Bearer` 请求头——每个请求自动带上，获取 token 的端点本身则自动跳过该头部；
3. **缓存**：token 持久化在 `pten_token.json`，缓存键为 `fs_<sha1(app_id+app_secret)>`，有效期取自飞书响应里的 `expire` 字段（缺省 7200 秒），而不是写死——平台调整有效期时不会误判。进程内还有一层内存缓存，避免每次都读文件；
4. **刷新重试**：命中 token 不合法（`99991661`）或已过期（`99991663`）时，自动刷新 token 并重试，最多 3 次。

顺带一提，这次改动还把 `Keys` 的 token 缓存从"单 token"升级成了**多 token 字典**——企业微信、飞书（乃至未来更多厂商）的 token 以各自凭证的哈希为键存在一起，一个 `Keys` 实例（以及它的 token 缓存文件）可以被多个模块共享：

```python
from pten.keys import Keys
from pten.fs_messager import FsAppMsgSender
from pten.wwmessager import AppMsgSender

keys = Keys("pten_keys.ini")          # 一份配置、一份 token 缓存
fs_app = FsAppMsgSender(keys=keys)    # 飞书应用消息
ww_app = AppMsgSender(keys=keys)      # 企业微信应用消息
```

## 7. 注意事项

- **权限没生效**：开了 `im:message` 权限但没发布应用版本，调用会被拒；
- **接收者不在可用范围**：把接收者加入应用的可用范围即可；
- **ID 类型传错**：`ou_` 开头是 open_id，`oc_` 开头是 chat_id，类型和 ID 不匹配会报"接收者不存在"之类的错误；
- **换个目录跑就报找不到 token**：token 缓存 `pten_token.json` 相对 CWD 解析，换目录相当于换了缓存（重新取一次 token 也能自愈，只是多一次请求）。

## 8. 小结

- 自建应用消息补齐了 pten 飞书侧"点对点触达"的能力，配合原有的 webhook 机器人，广播和单发都有了。
- 0.4.9 之后飞书多维表格（Base）的增删改查也通过 `FsBitable` 开放出来了——把告警写进多维表格做跟踪、再发条卡片消息通知负责人，一条链路都能用 pten 搞定，有兴趣可以继续深入。
