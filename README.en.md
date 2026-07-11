
# pten

**pten** is a Python library designed for convenient and quick use of the WeChat Work and Feishu APIs.

github: [https://github.com/bendell02/pten](https://github.com/bendell02/pten)  
gitee: [https://gitee.com/bendell02/pten](https://gitee.com/bendell02/pten)

## 1. Installation

```bash
pip install pten
```

Or install from source.

## 2. Basic Usage -- Example of Sending Messages via WeChat Work Bot

### 2.1 Configuring the Configuration File
The default path for the configuration file is `pten_keys.ini`, but you can specify a different path using the `keys_filepath` parameter.
For the complete content of the configuration file, refer to [Configuration File](#configuration-file). Not all fields need to be set; configure them as needed.  
For example, if you only use the WeChat Work bot, you only need to configure the `webhook_key` field under the `ww` section.
```ini
[ww]
webhook_key=7ande764-52a4-43d7-a252-05e8abcdb863
```

### 2.2 Getting Started
```python
from pten.wwmessager import BotMsgSender

bot = BotMsgSender() # Defaults to using the pten_keys.ini configuration file
# bot = BotMsgSender("another_pten_keys.ini") 

# Sending a text message
response = bot.send_text("hello world") 

# Sending a markdown message
markdown_content = '<font color="info">Hello world</font>'
response = bot.send_markdown(markdown_content)

# Sending an image message
image_path = "sample_image.png"
response = bot.send_image(image_path)

# You can also send voice messages, news messages, file messages, etc.
```

## 3. Configuration File

Not all fields need to be set; configure them as needed.

### 3.1 Complete Configuration File Example
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

[proxies]
http=http://xxx:xxx@xxx.xxx.xxx.xxx:8888
https=http://xxx:xxx@xxx.xxx.xxx.xxx:8888

[notice]
;ai
deepseek_api_key=sk-0a6e5b4e8b4c0e1a5b6b8e0e4d5aefb
;weather
seniverse_api_key=v5bFw3o1pSmbGvuEN

```
### 3.2 Configuration File Field Descriptions
| section  | Field Name  | Field Description |
| -------- | -------- | -------- |
| ww   | app_aes_key   | The AES key for the app. Used for encrypting and decrypting messages sent and received by the app.|
|      | app_agentid   | The agent ID of the app. Used when the app sends messages.   |
|      | app_secret    | The secret of the app. Required for the server API to obtain the access_token.   |
|      | app_token     | The token of the app. Used for encrypting and decrypting messages sent and received by the app.  |
|      | contact_sync_secret     | The secret for the contact list. Required for some APIs in the contact module. Passed via the `contact_sync_secret` parameter in the Contact class.  |
|      | corpid        | The corp ID. Required for the server API to obtain the access_token.  |
|      | webhook_key   | The webhook key for the WeChat Work bot. Required when sending messages via the bot.  |
| fs   | webhook_key   | The webhook key for the Feishu bot. Required when sending messages via the Feishu bot.  |
| globals | debug_mode   | Set to True to enable debug mode, which provides more debugging information.  |
| proxies | http   | Set the HTTP proxy. Configure when a proxy is needed.  |
|         | https   | Set the HTTPS proxy. Configure when a proxy is needed.  |
| notice  | deepseek_api_key | The API key for Deepseek. Can be passed when using the Deepseek class to answer questions. |
|         | seniverse_api_key | The API key for Seniverse Weather. Can be passed when using the Weather class to fetch weather information. |

• Why are proxies needed? When are they used?  
> Because the WeChat Work API requires configuring trusted IPs, and only trusted IPs can call the API. If the local network's IP changes frequently, you would need to reconfigure the trusted IP each time you call the API, which is cumbersome. By configuring a proxy, you can route the WeChat Work API calls through the proxy and configure the proxy's IP as a trusted IP, thus avoiding this issue.

## 4. Module Usage Instructions

### 4.1 wwmessage Module : Sending Bot and App Messages
#### 4.1.1 Sending Bot Messages
```python
from pten.wwmessager import BotMsgSender

bot = BotMsgSender() # Defaults to using the pten_keys.ini configuration file

# Sending a text message
response = bot.send_text("hello world") 

# You can also send markdown messages, image messages, voice messages, news messages, file messages, etc.
```

#### 4.1.2 Sending App Messages
```python
from pten.wwmessager import AppMsgSender

app = AppMsgSender()

# Sending a text message
response = app.send_text("hello world from app")

# You can also send markdown messages, image messages, voice messages, news messages, file messages, template card messages, etc.
```

### 4.2 notice Module : Notification Features

#### 4.2.1 Fetching Weather and Notifying

You can configure notifications to be sent via the bot or app, with the default being printed to the console.

```python
from pten.notice import Weather
from pten.wwmessager import BotMsgSender

weather = Weather()
bot = BotMsgSender()

# Configuring the bot to send notifications
weather.set_report_func(bot.send_text)

# Adding cities to fetch weather for, multiple cities can be added
weather.add_city("Shenzhen", "Shenzhen")

# Sending weather notifications, can be scheduled via apscheduler to notify every morning
weather.report_weather()
```

#### 4.2.2 Birthday Reminders

• Supports both lunar and solar birthdays  
• Can configure notifications to be sent via the bot or app, with the default being printed to the console
• After a reminder, the schedule for the next day is automatically added
• Lunar birthdays automatically handle leap months

```python
from pten.notice import Birthday
from pten.wwmessager import BotMsgSender

from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
birthday = Birthday()

# Setting the scheduler
birthday.set_scheduler(scheduler)

# Configuring the bot to send notifications
bot = BotMsgSender()
birthday.set_report_func(bot.send_text)

# Adding a lunar birthday reminder
birthday.add_lunar_schedule(3, 15, who="Mary")
# Custom reminder content can be set via the greeting_words parameter
birthday.add_lunar_schedule(3, 15, who="Mary", greeting_words="Happy anniversary of Mary's arrival on Earth!")

# Adding a solar birthday reminder
birthday.add_solar_schedule(1, 12, who="Maria")

scheduler.start()
```

#### 4.2.3 Getting AI Responses

```python
from pten.notice import Deepseek

deepseek = Deepseek()
content = deepseek.get_completion("Briefly introduce Newton")
```

### 4.3 wwcrypt Module : Encrypting and Decrypting Messages
Module for encrypting and decrypting messages sent and received by the app.
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

### 4.4 wwcontact Module : Contact List Related APIs
```python
from pten.wwcontact import Contact

contact = Contact("pten_keys.ini")

userid = "userid"
response = contact.get_user(userid)

department_id = "2"
response = contact.get_user_simple_list(department_id)

department_id = "2"
response = contact.get_user_list(department_id)

## More contact list APIs can be found in the source code 
```

### 4.5 wwdoc Module : WeChat Work Document Related APIs

```python
from pten.wwdoc import Doc

wwdoc = Doc("pten_keys.ini")

# Creating a document
doc_type = 10
doc_name = "test_smart_table2"
admin_users = ["user_a", "user_b"]
response = wwdoc.create_doc(doc_type, doc_name, admin_users=admin_users)

# Adding a view to a smart sheet
docid = "your_docid"
sheet_id = "your_sheetid"
view_title = "view_title"
view_type = "VIEW_TYPE_GRID"
response = wwdoc.smartsheet_add_view(docid, sheet_id, view_title, view_type)

# Adding fields to a smart sheet
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

## More WeChat Work document APIs can be found in the source code 
```

### 4.6 wwapi Module : General APIs

If you can't find the API you want to call in other modules, you can use this module to call it.

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

### 4.7 fs_messager Module : Sending Feishu Bot Messages

A messaging module for Feishu custom bots (webhook). It mirrors the structure of `wwmessager`, but currently supports only the webhook approach and can send text messages and card messages. A successful response is indicated by `code == 0` and `msg == "success"`.

```python
from pten.fs_messager import BotMsgSender

bot = BotMsgSender()  # Defaults to pten_keys.ini, reads the webhook_key under [fs]

# Send a text message
response = bot.send_text("hello world")

# Send a card message (interactive). template is the header color theme, default blue; options include red/orange/yellow/green/indigo/grey
response = bot.send_card(title="Build Notice", content="**build #123** passed", template="green")
```

To call the low-level Feishu endpoints directly, use the `fs_api` module, the same way as `wwapi`:

```python
from pten.fs_api import BotApi, BOT_API_TYPE

api = BotApi("pten_keys.ini")
response = api.http_call(
    BOT_API_TYPE["WEBHOOK_SEND"],
    {"msg_type": "text", "content": {"text": "hello from feishu bot"}},
)
```