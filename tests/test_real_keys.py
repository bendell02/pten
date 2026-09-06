"""需要真实凭证（pten_keys.ini）的集成测试用例汇总。"""

import configparser
import datetime
import os
import threading
import time

import pytest
from apscheduler.schedulers.blocking import BlockingScheduler
from lunardate import LunarDate

from pten import logger
from pten.fs_api import FsCorpApi
from pten.fs_bitable import FsBitable
from pten.fs_messager import FsAppMsgSender, FsBotMsgSender
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

    api = FsCorpApi(key_filepath)
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

    app = FsAppMsgSender(key_filepath)
    response = app.send_text("hello world from app")
    print(response)
    assert_fs_response(response)


# ---------------------------------------------------------------------------
# test_fs_bitable.py —— 飞书多维表格真实接口
# ---------------------------------------------------------------------------
@pytest.fixture()
def fs_bitable_real():
    """构造真实凭证的 FsBitable；未开启真实 key 或缺配置文件时整体跳过。"""
    key_filepath = "pten_keys.ini"
    if not os.path.exists(key_filepath):
        pytest.skip(f"Key file not found: {key_filepath}")
    return FsBitable(key_filepath)


def _bitable_ids(bitable, *options):
    """从 [fs_bitable] 段读取真实资源 ID，未配置该段则跳过。"""
    try:
        keys = bitable.keys.get_keys("fs_bitable", list(options))
    except configparser.Error:
        pytest.skip("[fs_bitable] not configured in pten_keys.ini")
    return keys.values()


def test_fs_bitable_crud_chain(fs_bitable_real):
    """用真实凭证跑通多维表格的 4 个写操作。

    依次执行：创建多维表格 → 新增数据表 → 新增记录 → 删除记录，每步断言成功并提取下一步所需的 ID。
    注意：创建出的多维表格 app 与数据表不会被清理（删除 app 走云文档接口，超出本次范围），
    故 app 名带时间戳便于事后人工识别与清理。
    """
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    bitable = fs_bitable_real
    ts = time.strftime("%Y%m%d%H%M%S")

    # 1. 创建多维表格（含一张空数据表）
    resp = bitable.create_app(name=f"pten_autotest_{ts}")
    assert_fs_response(resp)
    app = resp["data"]["app"]
    app_token = app["app_token"]
    assert app_token
    print(f"[bitable] created app: {app.get('url')} (app_token={app_token})")

    # 2. 新增一个数据表（首字段为文本索引字段）
    resp = bitable.create_table(
        app_token=app_token,
        name=f"autotest_{ts}",
        fields=[{"field_name": "名称", "type": 1}],
    )
    assert_fs_response(resp)
    table_id = resp["data"]["table_id"]
    assert table_id
    print(f"[bitable] created table: table_id={table_id}")

    # 3. 新增一条记录
    resp = bitable.create_record(
        app_token=app_token,
        table_id=table_id,
        fields={"名称": f"record_{ts}"},
    )
    assert_fs_response(resp)
    record_id = resp["data"]["record"]["record_id"]
    assert record_id
    print(f"[bitable] created record: record_id={record_id}")

    # 4. 删除该记录
    resp = bitable.delete_record(
        app_token=app_token, table_id=table_id, record_id=record_id
    )
    assert_fs_response(resp)
    assert resp["data"]["deleted"] is True
    print(f"[bitable] deleted record: record_id={record_id}")


def test_fs_bitable_list_tables(fs_bitable_real):
    """列出数据表：新建一张表后，list_tables 的结果应包含该 table_id。"""
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    bitable = fs_bitable_real

    # 依赖已有的 app_token 与 table_id，确保 list_tables 能返回该 table_id
    app_token, table_id = _bitable_ids(bitable, "app_token", "table_id")

    resp = bitable.list_tables(app_token=app_token)
    assert_fs_response(resp)
    table_ids = [t["table_id"] for t in resp["data"].get("items", [])]
    assert table_id in table_ids
    print(f"[bitable] list_tables: {table_ids}")


def test_fs_bitable_delete_table(fs_bitable_real):
    """删除数据表：新建一张表后 delete_table 应成功。

    app 创建时自带一张默认表，故删自建表不会触发“多维表格中只剩最后一张表时不允许删除”。
    """
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    bitable = fs_bitable_real

    # 依赖已有的 app_token 与待删 table_id，确保 delete_table 能成功
    app_token, table_id = _bitable_ids(bitable, "app_token", "delete_table_id")

    resp = bitable.delete_table(app_token=app_token, table_id=table_id)
    assert_fs_response(resp)
    print(f"[bitable] delete_table: table_id={table_id}")


def test_fs_bitable_add_record(fs_bitable_real):
    """新增记录：新建表与记录后，create_record 应返回新的 record_id。"""
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    bitable = fs_bitable_real

    # 依赖已有的 app_token 与 table_id，确保 create_record 能成功
    app_token, table_id = _bitable_ids(bitable, "app_token", "table_id")

    ts = time.strftime("%Y%m%d%H%M%S")
    resp = bitable.create_record(
        app_token=app_token, table_id=table_id, fields={"名称": f"record_{ts}"}
    )
    assert_fs_response(resp)
    record_id = resp["data"]["record"]["record_id"]
    assert record_id
    print(f"[bitable] create_record: record_id={record_id}")


def test_fs_bitable_update_record(fs_bitable_real):
    """更新记录：新建表与记录后，update_record 应返回同一 record_id（增量更新）。"""
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    bitable = fs_bitable_real

    # 依赖已有的 app_token、table_id 与 record_id，确保 update_record 能成功
    app_token, table_id, record_id = _bitable_ids(
        bitable, "app_token", "table_id", "record_id"
    )

    ts = time.strftime("%Y%m%d%H%M%S")

    resp = bitable.update_record(
        app_token=app_token,
        table_id=table_id,
        record_id=record_id,
        fields={"名称": f"updated_{ts}"},
    )
    assert_fs_response(resp)
    assert resp["data"]["record"]["record_id"] == record_id
    print(f"[bitable] update_record: record_id={record_id}")
