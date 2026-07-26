# Release Notes
本文件记录 pten 各版本的变更情况。

## 0.4.2 - 2026-07-27
- feat: 增加能设置日志路径的功能
- refactor: 重构fs_api.py和wwapi.py的重复代码

## 0.4.1 - 2026-07-12
- 修改包的description

## 0.4.0 - 2026-07-12
- 飞书(Feishu)自定义机器人支持：新增 `fs_api`、`fs_messager` 模块，结构与 `wwapi`/`wwmessager` 平行，目前支持通过 webhook 发送文本消息(`send_text`)和卡片消息(`send_card`)。
- 配置文件新增 `[fs]` section，用于配置飞书机器人 `webhook_key`。

## 0.3.0 - 2025-03-13
- 完善 README 内容。

## 0.2.0 - 2025-03-13
- 调整配置文件字段的 section 和名称。

## 0.1.0 - 2025-03-12
- pten 初始版本，封装企业微信(WeChat Work) API，包含以下模块：
  - `keys`：配置文件读取与 access_token/jsapi_ticket 缓存。
  - `wwapi`：通用 API 封装（`BotApi`/`CorpApi`/`ServiceCorpApi`/`ServiceProviderApi`）。
  - `wwmessager`：机器人和应用消息发送（文本、markdown、图片、语音、图文、文件、卡片等）。
  - `wwcontact`：通讯录相关 API。
  - `wwdoc`：企业微信文档/智能表格/表单相关 API。
  - `wwcrypt`：应用收发消息加解密。
  - `notice`：通知功能（天气、生日提醒、DeepSeek）。
- 添加 MIT License。
