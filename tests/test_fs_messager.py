from .conftest import assert_fs_response
from pten.fs_messager import BotMsgSender


def test_bot_msg_sender(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"code": 0, "msg": "success"}

    bot = BotMsgSender("pten_keys_example.ini")

    response = bot.send_text(content="hello world")
    print(response)
    assert_fs_response(response)


def test_send_card(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"code": 0, "msg": "success"}

    bot = BotMsgSender("pten_keys_example.ini")

    response = bot.send_card(
        title="飞书卡片",
        content="**hello** world\n\n[https://www.baidu.com](https://www.baidu.com)",
    )
    print(response)
    assert_fs_response(response)
