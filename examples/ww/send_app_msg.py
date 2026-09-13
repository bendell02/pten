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
    # 把下面的 userid 换成企业通讯录里的真实成员，否则会因用户不存在而发送失败
    response = app.send_text("hello，有人找你", touser=["userid1", "userid2"])
    print(response)

    # 文本卡片消息：签名与 send_text 不同，需 title / description / url 三个参数
    response = app.send_card(
        title="通知", description="这是卡片正文", url="https://example.com"
    )
    print(response)

    # markdown、图片、语音、视频、文件、图文、模板卡片等消息类型同理，
    # 用法见 wwmessager.AppMsgSender
