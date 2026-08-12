# pten

**pten** 是一个方便快捷使用企业微信和飞书API的python工具库.

github: [https://github.com/bendell02/pten](https://github.com/bendell02/pten)  
gitee: [https://gitee.com/bendell02/pten](https://gitee.com/bendell02/pten)

## 1. 安装

```bash
pip install pten
```

或者源码安装

## 2. 基础使用 -- 以使用机器人发送消息为例

### 2.1 设置配置文件
配置文件默认路径为 `pten_keys.ini`，也可以通过 `keys_filepath` 参数指定配置文件路径。
配置文件完整内容请参考[配置文件](#3. 配置文件)，并非所有字段都需要设置，根据自己需要配置即可。  
比如如果只用企业微信机器人，只需配置 `ww`的`webhook_key`字段即可；只用飞书机器人，只需配置 `fs`的`webhook_key`字段即可。
```ini
[ww]
webhook_key=7ande764-52a4-43d7-a252-05e8abcdb863

[fs]
webhook_key=cb46342e-4ecb-436c-b91d-6abcabc8c033e
```

### 2.2 企业微信机器人
```python
from pten.wwmessager import BotMsgSender

bot = BotMsgSender() # 默认使用 pten_keys.ini 配置文件
# bot = BotMsgSender("another_pten_keys.ini") 

# 发送文本消息
response = bot.send_text("hello world") 

# 发送markdown消息
markdown_content = '<font color="info">Hello world</font>'
response = bot.send_markdown(markdown_content)

# 发送图片消息
image_path = "sample_image.png"
response = bot.send_image(image_path)

# 还可发送语音消息、图文消息、文件消息等
```

### 2.3 飞书机器人
```python
from pten.fs_messager import BotMsgSender

bot = BotMsgSender()  # 默认使用 pten_keys.ini，读取 [fs] 的 webhook_key
# bot = BotMsgSender("another_pten_keys.ini")

# 发送文本消息
response = bot.send_text("hello world")

# 发送卡片消息(interactive)，template 为头部配色模板，默认 blue，可选 red/orange/yellow/green/indigo/grey
response = bot.send_card(title="构建通知", content="**build #123** 成功", template="green")
```

飞书机器人目前仅支持 webhook 方式，可发送文本消息和卡片消息，更多说明见 4.7 节。

## 3. 配置文件

并非所有字段都需要设置，按需传入

### 3.1 完整配置文件样例
```ini
[ww]
app_aes_key=9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO
app_agentid=1000005
app_secret=jVJF_EBWCVA_KVi_89YnY1T1bPD8-0PdqQ2rXc_Pgmj5
app_token=zJdPmXg8E4J1mMdnzP8d
contact_sync_secret=G4PC19fIwfsykabdv_drNVlOIe_crBvay3sUX8DhGss
corpid=wwdb63ff5ae01cd4b4
webhook_key=7ande764-52a4-43d7-a252-05e8abcdb863

[fs]
webhook_key=cb46342e-4ecb-436c-b91d-6abcabc8c033e

[globals]
debug_mode=False
;log_path=pten.log  ; 可选，日志文件路径，默认 pten.log（相对 CWD）

[proxies]
http=http://xxx:xxx@xxx.xxx.xxx.xxx:8888
https=http://xxx:xxx@xxx.xxx.xxx.xxx:8888

[notice]
;ai - 通用大模型(OpenAI兼容)，LLM 类未直接传参时从此读取
;llm_base_url=https://api.deepseek.com
;llm_api_key=sk-xxxxxxxx
;llm_model=deepseek-v4-flash
;deepseek_api_key 仅供 Deepseek 类使用，建议改用 LLM 类
deepseek_api_key=sk-0a6e5b4e8b4c0e1a5b6b8e0e4d5aefb
;weather
seniverse_api_key=v5bFw3o1pSmbGvuEN

;命名 LLM provider(OpenAI 兼容)，每个 [llm:<name>] 段对应一套模型配置
;用 LLM(provider="<name>") 按名字选用；可用 Keys.list_llm_providers() 枚举
;[llm:deepseek]
;base_url=https://api.deepseek.com
;api_key=sk-xxxxxxxx
;model=deepseek-v4-flash
;
;[llm:openai]
;base_url=https://api.openai.com/v1
;api_key=sk-xxxxxxxx
;model=gpt-4o-mini
```
### 3.2 配置文件字段说明
| section  | 字段名称  | 字段说明 |
| -------- | -------- | -------- |
| ww   | app_aes_key   | 应用的aes_key。应用收发消息加解密时使用|
|      | app_agentid   | 应用的agentid。应用发消息时使用   |
|      | app_secret    | 应用的secret。服务端API获取access_token时需要使用   |
|      | app_token     | 应用的token。应用收发消息加解密时使用  |
|      | contact_sync_secret     | 通讯录的secret。使用通讯录模块时部分API需要使用该secret。通过Contact的contact_sync_secret参数传入  |
|      | corpid        | corpid。服务端API获取access_token时需要使用  |
|      | webhook_key   | 企业微信机器人的webhook_key。使用机器人发消息时需要使用  |
| fs   | webhook_key   | 飞书机器人的webhook_key。使用飞书机器人发消息时需要使用  |
| globals | debug_mode   | 设置为True时开启调试模式，多一些调试信息  |
|         | log_path     | 日志文件路径，默认 pten.log（相对 CWD）。创建 Keys 实例时从其使用的配置文件读取；也可调用 ``pten.setup_logging()`` 显式配置  |
| proxies | http   | 设置http代理。需要走代理时设置即可  |
|         | https   | 设置https代理。需要走代理时设置即可  |
| notice  | llm_base_url | 通用大模型(OpenAI兼容)服务地址。LLM类未直接传入 base_url 时从此读取 |
|         | llm_api_key | 通用大模型(OpenAI兼容)的 api_key。LLM类未直接传入 api_key 时从此读取 |
|         | llm_model | 通用大模型(OpenAI兼容)的模型名称。LLM类未直接传入 model 时从此读取 |
|         | deepseek_api_key | deepseek 的 api_key，仅供 `Deepseek` 类使用。建议改用 `LLM` 类配合 `llm_*` 配置 |
|         | seniverse_api_key | 心知天气的api_key。使用Weather类获取天气时可传入 |
| llm:<name> | base_url | 命名 provider 的 OpenAI 兼容服务地址。`LLM(provider="<name>")` 时从此段读取 |
|         | api_key | 命名 provider 的 api_key。`LLM(provider="<name>")` 时从此段读取 |
|         | model | 命名 provider 的模型名称。`LLM(provider="<name>")` 时从此段读取 |

- 为什么需要proxies？ 什么情况使用？  
> 因为企业微信API是需要配置可信ip，只有可信ip才能调用API。如果本地网络的ip经常变，那么每次调用API都需要重新配置可信ip，比较麻烦。可以配置代理，让企业微信API调用时走代理，把代理的ip配置到可信ip里，这样就可以避免这个问题。

## 4. 各个模块使用说明

### 4.1 wwmessage 模块 : 发送机器人和应用消息
#### 4.1.1 机器人发送消息
```python
from pten.wwmessager import BotMsgSender

bot = BotMsgSender() # 默认使用 pten_keys.ini 配置文件

# 发送文本消息
response = bot.send_text("hello world") 

# 还可发送markdown消息、图片消息、语音消息、图文消息、文件消息等
```

#### 4.1.2 应用发送消息
```python
from pten.wwmessager import AppMsgSender

app = AppMsgSender()

# 发送文本消息
response = app.send_text("hello world from app")

# 还可发送markdown消息、图片消息、语音消息、图文消息、文件消息、模板卡片消息等
```

### 4.2 notice 模块 : 通知功能

#### 4.2.1 获取天气并通知

可配置通过机器人或者应用发送通知，默认打印在控制台

```python
from pten.notice import Weather
from pten.wwmessager import BotMsgSender

weather = Weather()
bot = BotMsgSender()

# 配置通过机器人来发送通知
weather.set_report_func(bot.send_text)

# 添加要获取天气的城市，可添加多个
weather.add_city("深圳", "Shenzhen")

# 发送天气通知，可通过apscheduler定时调用，每天早上通知天气信息
weather.report_weather()
```

#### 4.2.2 生日提醒

- 农历生日和阳历生日都支持  
- 可配置通过机器人或者应用发送通知，默认打印在控制台
- 提醒过后会自动添加下一天的提醒schedule
- 农历生日会自动处理闰月情况


```python
from pten.notice import Birthday
from pten.wwmessager import BotMsgSender

from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
birthday = Birthday()

# 设置定时器
birthday.set_scheduler(scheduler)

# 设置通过机器人来发送通知
bot = BotMsgSender()
birthday.set_report_func(bot.send_text)

# 添加农历生日提醒
birthday.add_lunar_schedule(3, 15, who="玛丽")
# 可定制提醒内容，填写 greeting_words 参数
birthday.add_lunar_schedule(3, 15, who="玛丽", greeting_words="玛丽来到地球纪念日，生快！")

# 添加阳历生日提醒
birthday.add_solar_schedule(1, 12, who="玛莉亚")

scheduler.start()
```

#### 4.2.3 获取ai的回答

`LLM` 是通用的 OpenAI 兼容大模型对话类，传入 `base_url`、`api_key`、`model` 即可对话，适配 DeepSeek、OpenAI 等不同模型：

```python
from pten.notice import LLM

# 直接传参即可对话，适配任意 OpenAI 兼容服务
llm = LLM(base_url="https://api.deepseek.com", api_key="sk-xxx", model="deepseek-v4-flash")
content = llm.get_completion("简略介绍一下牛顿")

# 换用其他模型只需改参数
# gpt = LLM(base_url="https://api.openai.com/v1", api_key="sk-xxx", model="gpt-4o-mini")
```

也可将 `llm_base_url`、`llm_api_key`、`llm_model` 配置在 `[notice]` 中，省略参数直接 `LLM()` 读取。

#### 4.2.4 配置多套 LLM provider

当需要同时使用多个模型（如 DeepSeek、OpenAI、本地模型各一套）时，可以为每个 provider 配置一个 `[llm:<name>]` 段，再用 `LLM(provider="<name>")` 按名字切换，无需在代码里硬编码地址和密钥：

```ini
[llm:deepseek]
base_url=https://api.deepseek.com
api_key=sk-deepseek-xxxxxxxx
model=deepseek-v4-flash

[llm:openai]
base_url=https://api.openai.com/v1
api_key=sk-openai-xxxxxxxx
model=gpt-4o-mini
```

```python
from pten.notice import LLM

# 按名字选用对应 provider，参数全部从 [llm:<name>] 段读取
deepseek = LLM(provider="deepseek")
print(deepseek.get_completion("用一句话介绍黑洞"))

openai = LLM(provider="openai")
print(openai.get_completion("Translate 'hello' to French"))

# 显式传入的参数始终优先于配置，方便临时覆盖某个字段
gpt4 = LLM(provider="openai", model="gpt-4o")
```

- 每个 `[llm:<name>]` 段需配置 `base_url`、`api_key`、`model`，三者缺一会抛 `ValueError`。`system_prompt` 作为构造参数传入，未传时默认 `"You are a helpful assistant"`。
- `provider` 名写错或段内缺键时，报错信息会列出当前可用的 provider，便于定位。
- 可用 `Keys.list_llm_providers()` 枚举配置文件中所有 `[llm:<name>]` 段的名字。
- 不传 `provider` 时仍走 `[notice]` 的 `llm_*` 默认配置，向后兼容。

```python
from pten.keys import Keys

keys = Keys()
print(keys.list_llm_providers())  # 例如 ['deepseek', 'openai']
```

> `Deepseek` 类已由更通用的 `LLM` 类替代，建议改用 `LLM`。`Deepseek` 仍保留以兼容旧代码。

### 4.3 wwcrypt 模块 : 加解密消息
应用收发消息加解密模块
```python
from pten.keys import Keys
from pten.wwcrypt import WXBizMsgCrypt

keys = Keys()
CORP_ID = keys.get_key("ww", "corpid")
API_TOKEN = keys.get_key("ww", "app_token")
API_AES_KEY = keys.get_key("ww", "app_aes_key")
wxcpt = WXBizMsgCrypt(API_TOKEN, API_AES_KEY, CORP_ID)

# VerifyURL
# ...
ret, sEchoStr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)

# DecryptMsg
# ...
body = await request.body()
ret, sMsg = wxcpt.DecryptMsg(body.decode("utf-8"), msg_signature, timestamp, nonce)

# EncryptMsg
# ...
ret, send_msg = wxcpt.EncryptMsg(sReplyMsg=sRespData, sNonce=nonce)

```

### 4.4 wwcontact 模块 : 通讯录相关API
```python
from pten.wwcontact import Contact

contact = Contact("pten_keys.ini")

userid = "userid"
response = contact.get_user(userid)

department_id = "2"
response = contact.get_user_simple_list(department_id)

department_id = "2"
response = contact.get_user_list(department_id)

## 更多通讯录API可参考源码 
```

### 4.5 wwdoc 模块 : 企业微信文档相关API

```python
from pten.wwdoc import Doc

wwdoc = Doc("pten_keys.ini")

# 创建文档
doc_type = 10
doc_name = "test_smart_table2"
admin_users = ["user_a", "user_b"]
response = wwdoc.create_doc(doc_type, doc_name, admin_users=admin_users)

# 智能表格添加视图
docid = "your_docid"
sheet_id = "your_sheetid"
view_title = "view_title"
view_type = "VIEW_TYPE_GRID"
response = wwdoc.smartsheet_add_view(docid, sheet_id, view_title, view_type)

# 智能表格添加字段
fields = [{"field_title": "TITLE", "field_type": "FIELD_TYPE_TEXT"}]
response = wwdoc.smartsheet_add_fields(docid, sheet_id, fields)
assert_response(response)
fields = [
    {
        "field_title": "number",
        "field_type": "FIELD_TYPE_NUMBER",
        "property_number": {"decimal_places": 2, "use_separate": False},
    }
]
response = wwdoc.smartsheet_add_fields(docid, sheet_id, fields)

## 更多企业微信文档API可参考源码 
```

### 4.6 wwapi 模块 : 通用API

如果在其他模块中找不到想调用的api，可通过此模块调用

#### 4.6.1 BotApi  BOT_API_TYPE
```python
from pten.wwapi import BotApi, BOT_API_TYPE

api = BotApi("pten_keys.ini")
response = api.http_call(
    BOT_API_TYPE["WEBHOOK_SEND"],
    {"msgtype": "text", "text": {"content": "hello from bot"}},
)
```


#### 4.6.2 CorpApi  CORP_API_TYPE
```python
from pten.wwapi import CorpApi, CORP_API_TYPE

api = CorpApi("pten_keys.ini")
response = api.http_call(CORP_API_TYPE["DEPARTMENT_LIST"])

corp_jsapi_ticket = api.get_corp_jsapi_ticket()
app_jsapi_ticket = api.get_app_jsapi_ticket()
```

### 4.7 fs_messager 模块 : 发送飞书机器人消息

飞书自定义机器人(webhook)消息发送模块，结构与 `wwmessager` 类似，但目前仅支持 webhook 方式，可发送文本消息和卡片消息。响应成功判定为 `code == 0`、`msg == "success"`。

```python
from pten.fs_messager import BotMsgSender

bot = BotMsgSender()  # 默认使用 pten_keys.ini，读取 [fs] 的 webhook_key

# 发送文本消息
response = bot.send_text("hello world")

# 发送卡片消息(interactive)，template 为头部配色模板，默认 blue，可选 red/orange/yellow/green/indigo/grey
response = bot.send_card(title="构建通知", content="**build #123** 成功", template="green")
```

如需直接调用飞书底层接口，可使用 `fs_api` 模块，用法与 `wwapi` 一致：

```python
from pten.fs_api import BotApi, BOT_API_TYPE

api = BotApi("pten_keys.ini")
response = api.http_call(
    BOT_API_TYPE["WEBHOOK_SEND"],
    {"msg_type": "text", "content": {"text": "hello from feishu bot"}},
)
```