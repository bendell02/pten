from .conftest import assert_fs_response, create_fs_mock_response
import json
from pten.fs_messager import BotMsgSender, AppMsgSender
from pten.keys import Keys


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


def test_app_msg_sender(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    app = AppMsgSender(keys=fs_keys)
    response = app.send_text("hello world from app", receive_id="ou_test")

    assert_fs_response(response)
    # 发往 im/v1/messages，receive_id_type 默认 open_id
    assert mock_post.call_args.args[0] == (
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    )
    # im 接口要求 content 为 JSON 字符串
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body == {
        "receive_id": "ou_test",
        "msg_type": "text",
        "content": '{"text": "hello world from app"}',
    }
    # 鉴权头由 CorpApi 自动携带
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer t-fake"


def test_app_msg_sender_receive_id_type(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    app = AppMsgSender(keys=fs_keys)
    response = app.send_text(
        "hello group", receive_id="oc_test", receive_id_type="chat_id"
    )

    assert_fs_response(response)
    # receive_id_type 作为查询参数替换进 URL
    assert mock_post.call_args.args[0].endswith(
        "im/v1/messages?receive_id_type=chat_id"
    )


def test_app_msg_send_card(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    app = AppMsgSender(keys=fs_keys)
    response = app.send_card(
        title="飞书卡片", content="**hello** world", receive_id="ou_test"
    )

    assert_fs_response(response)
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body["msg_type"] == "interactive"
    # 卡片整体序列化进 content
    card = json.loads(body["content"])
    assert card["header"]["title"]["content"] == "飞书卡片"
    assert card["elements"][0]["text"]["content"] == "**hello** world"


def test_app_msg_sender_default_receive_id(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    app = AppMsgSender(keys=fs_keys)
    # 未显式传 receive_id 时回退 [fs] 配置的默认接收者
    response = app.send_text("hello default receiver")

    assert_fs_response(response)
    assert mock_post.call_args.args[0].endswith(
        "im/v1/messages?receive_id_type=open_id"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body["receive_id"] == fs_keys.get_key("fs", "receive_id")


def test_app_msg_sender_default_receive_id_type(mocker, tmp_path):
    # 默认接收者是群聊时，[fs] 可一并配置 receive_id_type
    ini = tmp_path / "keys_chat_default.ini"
    ini.write_text(
        "[fs]\napp_id=cli_x\napp_secret=s\n"
        "receive_id=oc_default_group\nreceive_id_type=chat_id\n",
        encoding="utf-8",
    )
    keys = Keys(str(ini))
    keys.TOKEN_PATH = tmp_path / "pten_token.json"

    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = create_fs_mock_response({"code": 0, "msg": "success"})

    app = AppMsgSender(keys=keys)
    response = app.send_text("hello group")

    assert_fs_response(response)
    assert mock_post.call_args.args[0].endswith(
        "im/v1/messages?receive_id_type=chat_id"
    )
    body = json.loads(mock_post.call_args.kwargs["data"])
    assert body["receive_id"] == "oc_default_group"


def test_app_msg_sender_no_receive_id(mocker, fs_keys_no_receiver):
    mock_post = mocker.patch("requests.post")

    app = AppMsgSender(keys=fs_keys_no_receiver)
    response = app.send_text("hello world")

    # 既没有传参也没有配置默认接收者：不发请求，直接返回错误
    assert response == {"code": -1, "msg": app.errmsgs["receive_id_error"]}
    assert mock_post.call_count == 0


def test_app_msg_sender_empty_content(mocker, fs_keys):
    mock_post = mocker.patch("requests.post")

    app = AppMsgSender(keys=fs_keys)
    response = app.send_text("", receive_id="ou_test")

    assert response == {"code": -1, "msg": app.errmsgs["text_error"]}
    assert mock_post.call_count == 0
