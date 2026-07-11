from .conftest import assert_response
from pathlib import Path
from pten.wwmessager import BotMsgSender, AppMsgSender


def test_bot_msg_sender(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}

    bot = BotMsgSender("pten_keys_example.ini")
    current_dir = Path(__file__).resolve().parent

    response = bot.send_text(content="hello world")
    assert_response(response)

    markdown_content = '<font color="info">Hello world</font>'
    response = bot.send_markdown(markdown_content)
    assert_response(response)

    image_path = str(current_dir) + "/sample_data/sample_image.png"
    response = bot.send_image(image_path)
    assert_response(response)

    voice_path = str(current_dir) + "/sample_data/sample_voice.amr"
    response = bot.send_voice(voice_path)
    assert_response(response)

    title = "中秋节礼品领取"
    description = "今年中秋节公司有豪礼相送"
    link_url = "www.qq.com"
    picurl = "http://res.mail.qq.com/node/ww/wwopenmng/images/independent/doc/test_pic_msg1.png"
    response = bot.send_news(title, description, link_url, picurl)
    assert_response(response)

    file_path = str(current_dir) + "/sample_data/sample_file.txt"
    response = bot.send_file(file_path)
    assert_response(response)


def test_app_msg_sender(mocker):
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {
        "errcode": 0,
        "errmsg": "ok",
        "access_token": "fake_token",
    }

    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {
        "errcode": 0,
        "errmsg": "ok",
        "chatid": "chatid",
    }

    app = AppMsgSender("pten_keys_example.ini")
    current_dir = Path(__file__).resolve().parent

    response = app.send_text("hello world from app")
    assert_response(response)

    markdown_content = '<font color="info">Hello world</font>'
    response = app.send_markdown(markdown_content)
    assert_response(response)

    image_path = str(current_dir) + "/sample_data/sample_image.png"
    response = app.send_image(image_path)
    assert_response(response)

    voice_path = str(current_dir) + "/sample_data/sample_voice.amr"
    response = app.send_voice(voice_path)
    assert_response(response)

    video_path = str(current_dir) + "/sample_data/sample_video.mp4"
    response = app.send_video(video_path)
    assert_response(response)

    title = "中秋节礼品领取"
    description = "今年中秋节公司有豪礼相送"
    link_url = "www.qq.com"
    picurl = "http://res.mail.qq.com/node/ww/wwopenmng/images/independent/doc/test_pic_msg1.png"
    response = app.send_news(title, description, link_url, picurl)
    assert_response(response)

    file_path = str(current_dir) + "/sample_data/sample_file.txt"
    response = app.send_file(file_path)
    assert_response(response)

    title = "Hello"
    image_path = str(current_dir) + "/sample_data/sample_image.png"
    content = '<a href="https://www.qq.com">Hello World</a>'
    author = "author"
    content_source_url = "https://www.qq.com"
    digest = "description"
    response = app.send_mpnews(
        title, image_path, content, author, content_source_url, digest
    )
    assert_response(response)

    title = "Hello"
    description = "description"
    url = "https://www.qq.com"
    response = app.send_card(title, description, url, touser=["PengYong"])
    assert_response(response)

    name = "chatid"
    owner = "owner"
    userlist = ["user1", "user2"]
    chatid = "chatid"
    show_chat = True
    response = app.create_chat(name, owner, userlist, chatid, show_chat)
    assert_response(response)

    chatid = "chatid"
    response = app.send_text(content="hello world from app", chatid=chatid)
    assert_response(response)


def test_send_template_card(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}

    sender = BotMsgSender("pten_keys_example.ini")  # or sender = AppMsgSender()

    # template_card_text_notice
    template_card = {
        "card_type": "text_notice",
        "source": {
            "icon_url": "https://wework.qpic.cn/wwpic/252813_jOfDHtcISzuodLa_1629280209/0",
            "desc": "企业微信",
            "desc_color": 0,
        },
        "main_title": {
            "title": "欢迎使用企业微信",
            "desc": "您的好友正在邀请您加入企业微信",
        },
        "emphasis_content": {"title": "100", "desc": "数据含义"},
        "sub_title_text": "下载企业微信还能抢红包！",
        "card_action": {"type": 1, "url": "https://work.weixin.qq.com/?from=openApi"},
    }
    response = sender.send_template_card(template_card)
    assert_response(response)

    # template_card_news_notice
    template_card = {
        "card_type": "news_notice",
        "source": {
            "icon_url": "https://wework.qpic.cn/wwpic/252813_jOfDHtcISzuodLa_1629280209/0",
            "desc": "企业微信",
            "desc_color": 0,
        },
        "main_title": {
            "title": "欢迎使用企业微信",
            "desc": "您的好友正在邀请您加入企业微信",
        },
        "card_image": {
            "url": "https://wework.qpic.cn/wwpic/354393_4zpkKXd7SrGMvfg_1629280616/0",
            "aspect_ratio": 2.25,
        },
        "image_text_area": {
            "type": 1,
            "url": "https://work.weixin.qq.com",
            "title": "欢迎使用企业微信",
            "desc": "您的好友正在邀请您加入企业微信",
            "image_url": "https://wework.qpic.cn/wwpic/354393_4zpkKXd7SrGMvfg_1629280616/0",
        },
        "vertical_content_list": [
            {"title": "惊喜红包等你来拿", "desc": "下载企业微信还能抢红包！"}
        ],
        "horizontal_content_list": [
            {"keyname": "邀请人", "value": "张三"},
            {
                "keyname": "企微官网",
                "value": "点击访问",
                "type": 1,
                "url": "https://work.weixin.qq.com/?from=openApi",
            },
        ],
        "jump_list": [
            {
                "type": 1,
                "url": "https://work.weixin.qq.com/?from=openApi",
                "title": "企业微信官网",
            }
        ],
        "card_action": {"type": 1, "url": "https://work.weixin.qq.com/?from=openApi"},
    }
    response = sender.send_template_card(template_card)
    assert_response(response)
