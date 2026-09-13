"""企业微信机器人（webhook）发消息示例。

运行前提：[ww] 配置 webhook_key。
运行方式：python examples/ww/send_bot_msg.py
"""

from pten.wwmessager import BotMsgSender

if __name__ == "__main__":
    # 不传参数时按查找链定位配置文件：
    # PTEN_KEYS_FILE 环境变量 → ./pten_keys.ini → ~/.pten/pten_keys.ini
    bot = BotMsgSender()

    # 文本消息；mentioned_list 可提醒指定成员（userid），["@all"] 提醒所有人
    response = bot.send_text("hello from pten", mentioned_list=["@all"])
    print(response)

    # markdown 消息，支持企业微信 markdown 语法
    response = bot.send_markdown('**hello** <font color="info">markdown</font>')
    print(response)

    # 其余消息类型（图片 send_image / 图文 send_news / 文件 send_file /
    # 语音 send_voice / 模板卡片 send_template_card）用法见 wwmessager.BotMsgSender
