"""需要真实凭证（pten_keys.ini）的集成测试用例汇总。"""

import datetime
import os
import threading
import time

import pytest
from apscheduler.schedulers.blocking import BlockingScheduler
from lunardate import LunarDate

from pten import logger
from pten.fs_api import CorpApi
from pten.fs_messager import AppMsgSender
from pten.fs_messager import BotMsgSender as FsBotMsgSender
from pten.keys import Keys
from pten.notice import LLM, Birthday, Weather
from pten.wwapi import BOT_API_TYPE, BotApi
from pten.wwcrypt import WXBizMsgCrypt
from pten.wwmessager import BotMsgSender

from .conftest import assert_fs_response, enable_long_time_tests, use_real_keys


# ---------------------------------------------------------------------------
# test_wwapi.py —— 企业微信 Bot webhook
# ---------------------------------------------------------------------------
def test_ww_bot_api():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    api = BotApi()
    response = api.http_call(
        BOT_API_TYPE["WEBHOOK_SEND"],
        {"msgtype": "text", "text": {"content": "hello from bot"}},
    )
    assert response["errcode"] == 0
    assert response["errmsg"] == "ok"


# ---------------------------------------------------------------------------
# test_wwcrypt.py —— 回调消息加解密（依赖真实 corpid / app_token / app_aes_key）
# ---------------------------------------------------------------------------
@pytest.fixture()
def wwcpt():
    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    keys = Keys(key_filepath)
    CORP_ID = keys.get_key("ww", "corpid")
    API_TOKEN = keys.get_key("ww", "app_token")
    API_AES_KEY = keys.get_key("ww", "app_aes_key")

    wwcpt = WXBizMsgCrypt(API_TOKEN, API_AES_KEY, CORP_ID)
    return wwcpt


def test_ww_VerifyURL(wwcpt):
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    msg_signature = "fa256ca984aa648c058fe106d9fb766cb5271299"
    timestamp = "1740712860"
    nonce = "1741290221"
    echostr = "ZiukUpbK6YHaHAQ2FFKciqqehcgztxpA0qd4PHf4jCS/xZ4Yw0IF+utac04PF4HqB7bKNF+7h1qsaZRKUjoZWA=="
    echo_str_expected = b"7805676074021366686"
    ret, echo_str_decrypted = wwcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
    assert ret == 0
    assert echo_str_decrypted == echo_str_expected


def test_ww_DecryptMsg(wwcpt):
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    sPostData = "<xml><ToUserName><![CDATA[wwdb36ffe501dc44ba]]></ToUserName><Encrypt><![CDATA[Lc2M6ZsoQ08Us9UdegINhn4NOAj64Rtecn8onJ544OsSgkLX5O16XqtnO0xkc0cE3fzgy5vXZd/CZPtmAJlXaR1qfIINKm+w3J8LP17WnuD98MvkwHO5Vje1n69GouXU+fYujCtsd2TM8L7exzuooJXJao1mqpvUqHMUArvRvo+XVcyXSbBhWB+rzj8zcVSwu4JSzPxwdqVk2Q3GNVVxaDw8DfH0nhivjEeLdlD0IaDCw2pNn62lLpHZvZ52T+AV1HvIj+OZ4QvQ6cw3Ntr9gtpAuaA/HQbqXNT7pYCUss4KqmFAGjkVAH88ceF5iL7DrI4oPTTTzZ43DD3YK07bRdJU7w5j/H+b2oRFru8Q+RQFnh+jsTQIGR39gWHRr1qYJZr8ixeKuA2OZYLe84yRkhZA8EFUdUwIgW9lPyDK4Ew=]]></Encrypt><AgentID><![CDATA[1000005]]></AgentID></xml>"
    msg_signature = "89ab6f020ae9cf2792f04e6b535f92806dcaee14"
    timestamp = "1740718337"
    nonce = "1741092583"
    ret, sMsg = wwcpt.DecryptMsg(sPostData, msg_signature, timestamp, nonce)
    sMsg_expected = b"<xml><ToUserName><![CDATA[wwdb36ffe501dc44ba]]></ToUserName><FromUserName><![CDATA[PengYong]]></FromUserName><CreateTime>1740718337</CreateTime><MsgType><![CDATA[text]]></MsgType><Content><![CDATA[hello]]></Content><MsgId>7476328330859679818</MsgId><AgentID>1000005</AgentID></xml>"

    assert ret == 0
    assert sMsg == sMsg_expected


# ---------------------------------------------------------------------------
# test_notice.py —— LLM / 天气 / 生日定时提醒
# ---------------------------------------------------------------------------
def test_llm_real():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    llm = LLM(keys_filepath=key_filepath)
    content = llm.get_completion("你好")
    print(content)
    assert content != ""


def test_ww_weather_report():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    weather = Weather()
    bot = BotMsgSender()
    weather.set_report_func(bot.send_text)
    weather.add_city("深圳", "Shenzhen")
    weather.add_city("九江", "Jiujiang")
    weather.add_city("吉安", "Jian")
    weather.report_weather()


def test_ww_birthday():
    if not enable_long_time_tests:
        pytest.skip("enable_long_time_tests is False")

    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    scheduler = BlockingScheduler()
    birthday = Birthday()
    birthday.set_scheduler(scheduler)
    bot = BotMsgSender()
    birthday.set_report_func(bot.send_text)

    now = datetime.datetime.now()
    lunar_date = LunarDate.fromSolarDate(now.year, now.month, now.day)
    birthday.add_lunar_schedule(
        lunar_date.month,
        lunar_date.day,
        now.hour,
        now.minute + 1,
        who="test_luar_date",
    )

    birthday.add_solar_schedule(
        now.month, now.day, now.hour, now.minute + 1, who="test_solar_date"
    )

    def stop_scheduler():
        sleep_seconds = 61
        logger.warning(f"Scheduler will stop after {sleep_seconds} seconds")
        time.sleep(sleep_seconds)
        scheduler.shutdown(wait=False)

    stop_thread = threading.Thread(target=stop_scheduler)
    stop_thread.start()

    scheduler.start()


# ---------------------------------------------------------------------------
# test_fs_api.py —— 飞书 tenant_access_token
# ---------------------------------------------------------------------------
def test_fs_tenant_access_token():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    api = CorpApi(key_filepath)
    token = api.get_access_token()
    # 飞书的 tenant_access_token 以 t- 开头
    assert token and token.startswith("t-")


# ---------------------------------------------------------------------------
# test_fs_messager.py —— 飞书机器人卡片 / 应用消息
# ---------------------------------------------------------------------------
def test_fs_bot_send_card():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    bot = FsBotMsgSender(key_filepath)

    response = bot.send_card(
        title="飞书卡片",
        content="**hello** world for pytest\n\n[https://www.baidu.com](https://www.baidu.com)",
        template="red",
    )
    print(response)
    assert_fs_response(response)


def test_fs_app_msg_sender():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")

    app = AppMsgSender(key_filepath)
    response = app.send_text("hello world from app")
    print(response)
    assert_fs_response(response)
