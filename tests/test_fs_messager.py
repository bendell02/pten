from .conftest import assert_fs_response
import os
from pten.fs_messager import BotMsgSender
import pytest


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


def test_send_card_real():
    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    bot = BotMsgSender("pten_keys.ini")

    response = bot.send_card(
        title="飞书卡片",
        content="**hello** world for pytest\n\n[https://www.baidu.com](https://www.baidu.com)",
        template="red",
    )
    print(response)
    assert_fs_response(response)
