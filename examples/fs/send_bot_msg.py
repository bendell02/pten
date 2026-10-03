"""飞书机器人（webhook）发消息示例。

运行前提：[fs] 配置 webhook_key，或构造时直接传入 webhook_key。
运行方式：python examples/fs/send_bot_msg.py
"""

from pten.fs_messager import FsBotMsgSender

if __name__ == "__main__":
    # 不传参数时按查找链定位配置文件：
    # PTEN_KEYS_FILE 环境变量 → ./pten_keys.ini → ~/.pten/pten_keys.ini
    bot = FsBotMsgSender()

    # 机器人只需要 webhook_key，也可直接传入，无需配置文件：
    # bot = FsBotMsgSender(webhook_key="your-webhook-key")

    # 文本消息
    response = bot.send_text("hello from pten")
    print(response)

    # 卡片消息(interactive)；template 为头部配色，默认 blue，
    # 可选 red/orange/yellow/green/indigo/grey 等，content 支持 lark_md 语法
    response = bot.send_card(
        title="构建通知", content="**build #123** 成功", template="green"
    )
    print(response)
