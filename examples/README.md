# pten 示例代码

每个子目录按厂商/模块分组，每个 `.py` 文件是一个独立可运行的最小示例，
演示该模块最常用的用法。更完整的场景化教程见 `docs/` 目录。

## 运行前提

1. 安装 pten，两种方式任选其一：

   - 源码安装（推荐）：`pip install -e .` —— 随仓库代码更新，接口始终与示例一致
   - PyPI 安装：`pip install pten` —— 示例按仓库最新代码编写，
     若安装的发行版落后于仓库（新特性尚未发布），可能报 `ImportError` / `AttributeError`

2. 准备配置文件 `pten_keys.ini`（完整模板见 [pten_keys_example.ini](../pten_keys_example.ini)），
   查找顺序：`keys_filepath` 显式路径 → 环境变量 `PTEN_KEYS_FILE` → 当前目录 `./pten_keys.ini`
   → 用户主目录 `~/.pten/pten_keys.ini`（前两个不存在时直接报错，后两个依次探测）。
   按所用示例配置对应字段即可，例如只用企业微信机器人时，配 `[ww]` 的 `webhook_key` 就够了。

3. ⚠️ 示例会**真实调用 API**：消息会真的发出去，多维表格示例会真的建表写数据。
   请换成自己的 key、接收者再运行。

## 运行方式

在仓库根目录执行：

```bash
python examples/ww/send_bot_msg.py
```

Linux / macOS 上把 `python` 换成 `python3` 即可。

## 示例一览

| 示例 | 演示内容 | 所需配置 |
| ---- | -------- | -------- |
| `fs/send_bot_msg.py` | 飞书机器人（webhook）发文本 / 卡片 | `[fs]` webhook_key |
| `fs/send_app_msg.py` | 飞书自建应用发消息（显式 / 默认接收者） | `[fs]` app_id、app_secret（可选 receive_id、receive_id_type） |
| `fs/bitable_crud.py` | 飞书多维表格建表、记录增删改查 | `[fs]` app_id、app_secret |
| `notice/birthday.py` | 生日提醒（农历/阳历，apscheduler 定时） | 无（默认打印；接机器人通知需 `[ww]` webhook_key） |
| `notice/llm_chat.py` | LLM 对话（直传参数 / provider / 默认配置三种方式） | 脚本内常量，或 `[notice]` llm_*，或 `[llm:<name>]` |
| `notice/weather.py` | 心知天气查询与通知 | `[notice]` seniverse_api_key |
| `ww/send_bot_msg.py` | 企业微信机器人（webhook）发文本 / markdown | `[ww]` webhook_key |
| `ww/send_app_msg.py` | 企业微信自建应用发应用消息 | `[ww]` corpid、app_secret、app_agentid |

## 约定

- 示例用 `print` 直接打印响应。成功的判定：企业微信 `errcode == 0`，飞书 `code == 0`。
- 文件不以 `test_` 开头，不会被 pytest 收集；打包内容来自 `src/pten`，examples/ 不会进发行包。
- 新增示例时保持"一个文件只演示一个模块的最常用用法"，接口变更时同步维护对应示例。
