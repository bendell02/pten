from .conftest import assert_fs_response
from pten.fs_messager import BotMsgSender


def test_send_card_real():

    bot = BotMsgSender("pten_keys.ini")

    response = bot.send_card(
        title="飞书卡片",
        content="**hello** world\n\n[https://www.baidu.com](https://www.baidu.com)",
        template="indigo",
    )
    print(response)
    assert_fs_response(response)
