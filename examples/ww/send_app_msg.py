"""企业微信自建应用发应用消息示例。

运行前提：[ww] 配置 corpid、app_secret、app_agentid。
运行方式：python examples/ww/send_app_msg.py
"""

from pten.wwmessager import AppMsgSender

if __name__ == "__main__":
    app = AppMsgSender()

    # 不指定接收者时默认发给全体成员（@all）
    response = app.send_text("hello from pten app")
    print(response)

    # 指定接收者：touser / toparty / totag 均传列表
    response = app.send_text("hello，有人找你", touser=["userid1", "userid2"])
    print(response)

    # markdown、图片、语音、视频、文件、图文、卡片、模板卡片等消息类型同理，
    # 用法见 wwmessager.AppMsgSender
