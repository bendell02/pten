"""飞书自建应用发消息示例（FsAppMsgSender，tenant_access_token 鉴权）。

运行前提：[fs] 配置 app_id、app_secret（取 tenant_access_token 必需）；
        接收者把 RECEIVE_ID 换成你的 ID，或在 [fs] 配置默认 receive_id。
运行方式：python examples/fs/send_app_msg.py
"""

from pten.fs_messager import FsAppMsgSender

# 换成你的接收者 ID：open_id（ou_ 开头）/ user_id / union_id / email / 群聊 chat_id
RECEIVE_ID = "ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

if __name__ == "__main__":
    app = FsAppMsgSender()

    # 方式一：显式指定接收者及其 ID 类型（open_id/user_id/union_id/email/chat_id）
    response = app.send_text(
        "hello from pten app",
        receive_id=RECEIVE_ID,
        receive_id_type="open_id",
    )
    print(response)

    # 方式二：不传 receive_id，回退 [fs] 配置的默认接收者
    # （receive_id + 可选 receive_id_type；两者都未配置时返回错误 dict，不发起请求）
    response = app.send_text("发给默认接收者")
    print(response)

    # 卡片消息同理：同样可显式指定 receive_id，或省略回退 [fs] 默认接收者
    response = app.send_card(
        title="构建通知",
        content="**build #123** 成功",
        template="green",
        receive_id=RECEIVE_ID,
        receive_id_type="open_id",
    )
    print(response)
