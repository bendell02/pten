# Release Notes
本文件记录 pten 各版本的变更情况。


## v0.4.9 - 20260907
1. feat: 增加飞书多维表格的增删改查操作

## v0.4.8 - 20260906
1. refactor: 飞书的模块添加Fs前缀，避免与ww的重名

## v0.4.7 - 20260905
1. feat: 支持飞书应用以tenant身份发消息

## v0.4.6 - 20260813
1. feat: 一个配置文件里支持多套LLM provider

## 0.4.5 - 2026-08-11
- feat: Deepseek基于LLM类改写
- fix: 解决设置日志路径时的空pten.log问题

## 0.4.4 - 2026-08-02
- feat: `notice` 新增通用大模型对话类 `LLM`，传入 `base_url`/`api_key`/`model` 即可适配任意 OpenAI 兼容服务；`[notice]` 新增 `llm_base_url`/`llm_api_key`/`llm_model` 配置。建议以 `LLM` 替代 `Deepseek`。
- docs: README 与 CLAUDE.md 增加 `LLM` 类说明，标注 `Deepseek` 为已替代。

## 0.4.3 - 2026-07-27
- feat: README增加飞书机器人的样例

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
