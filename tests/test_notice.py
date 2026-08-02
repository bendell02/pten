from pten import logger
from .conftest import enable_long_time_tests, use_real_keys
from pten.notice import Birthday, Deepseek, LLM, Weather
from pten.wwmessager import BotMsgSender
import pytest

from apscheduler.schedulers.blocking import BlockingScheduler
import datetime
from lunardate import LunarDate
import os
import threading
import time


def test_deepseek(mocker):
    mock_get = mocker.patch("pten.notice.Deepseek.get_completion")
    mock_get.return_value = "newton"

    deepseek = Deepseek("pten_keys_example.ini")
    content = deepseek.get_completion("简略介绍一下牛顿")
    assert content != ""


def test_llm(mocker):
    mock_get = mocker.patch("pten.notice.LLM.get_completion")
    mock_get.return_value = "newton"

    llm = LLM(
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        model="deepseek-v4-flash",
        keys_filepath="pten_keys_example.ini",
    )
    content = llm.get_completion("简略介绍一下牛顿")
    assert content != ""


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


def test_weather(mocker):
    mock_get = mocker.patch("pten.notice.Weather.get_city_weather")
    mock_get.return_value = "good weather"

    weather = Weather("pten_keys_example.ini")
    weather_str = weather.get_city_weather("深圳", "Shenzhen")
    assert weather_str != ""


def test_weather_report():
    if not use_real_keys:
        pytest.skip("use_real_keys is False")

    weather = Weather()
    bot = BotMsgSender()
    weather.set_report_func(bot.send_text)
    weather.add_city("深圳", "Shenzhen")
    weather.add_city("九江", "Jiujiang")
    weather.add_city("吉安", "Jian")
    weather.report_weather()


def test_birthday_leap_month():
    assert Birthday.is_leap_month(2020, 4) is True
    assert Birthday.is_leap_month(2019, 4) is False


def test_birthday():
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
