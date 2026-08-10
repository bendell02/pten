"""
pten.notice
~~~~~~~~~~~~

This module implements the notice functions.

"""

from . import logger
from .keys import Keys
from apscheduler.schedulers.blocking import BaseScheduler
import configparser
import datetime
from lunardate import LunarDate
from openai import OpenAI
import requests
import json


class Notice:
    def __init__(self):
        self.report_func = print
        self.scheduler: BaseScheduler = None

    def set_report_func(self, func):
        self.report_func = func

    def set_scheduler(self, scheduler: BaseScheduler):
        self.scheduler = scheduler

    def report_text(self, text):
        self.report_func(text)


class Birthday(Notice):
    def __init__(self):
        super().__init__()

    @staticmethod
    def get_date_str_from_lunar_date(
        lunar_year, lunar_month, lunar_day, hour=8, minute=3, is_leap_month=False
    ):
        lunar_date = LunarDate(lunar_year, lunar_month, lunar_day, is_leap_month)
        solar_date = lunar_date.toSolarDate()
        return f"{solar_date} {hour:02d}:{minute:02d}:00"

    @staticmethod
    def is_leap_month(lunar_year, lunar_month):
        return lunar_month == LunarDate.leapMonthForYear(lunar_year)

    @staticmethod
    def get_now_lunar_date():
        now_solar_date = datetime.datetime.now()
        year = now_solar_date.year
        month = now_solar_date.month
        day = now_solar_date.day
        now_lunar_date = LunarDate.fromSolarDate(year, month, day)
        return now_lunar_date

    @staticmethod
    def generate_birthday_greeting(who, greeting_words=None):
        msg = f"今天是{who}的生日，让我们来祝福{who}吧"
        if greeting_words:
            msg = f"今天是{who}的生日，{greeting_words}"

        return msg

    def _add_lunar_schedule(
        self, msg, lunar_year, lunar_month, lunar_day, hour, minute
    ):
        run_date = self.get_date_str_from_lunar_date(
            lunar_year, lunar_month, lunar_day, hour, minute, False
        )
        args = [msg, lunar_month, lunar_day, hour, minute]
        func = self.report_lunar_birthday
        self.scheduler.add_job(func, "date", run_date=run_date, args=args)

        # solve leap month
        if not self.is_leap_month(lunar_year, lunar_month):
            return
        run_date = self.get_date_str_from_lunar_date(
            lunar_year, lunar_month, lunar_day, hour, minute, True
        )
        self.scheduler.add_job(func, "date", run_date=run_date, args=args)

    def _add_solar_schedule(self, msg, year, month, day, hour, minute):
        solar_date = datetime.date(year, month, day)
        run_date = f"{solar_date} {hour:02d}:{minute:02d}:00"
        args = [msg, month, day, hour, minute]
        func = self.report_solar_birthday
        self.scheduler.add_job(func, "date", run_date=run_date, args=args)

    def report_lunar_birthday(self, msg, lunar_month, lunar_day, hour=8, minute=3):
        self.report_func(msg)

        if self.scheduler is None:
            return

        # add next year's schedule job
        now_lunar_date = self.get_now_lunar_date()
        self._add_lunar_schedule(
            msg, now_lunar_date.year + 1, lunar_month, lunar_day, hour, minute
        )

    def report_solar_birthday(self, msg, month, day, hour=8, minute=3):
        self.report_func(msg)

        if self.scheduler is None:
            return

        # add next year's schedule job
        today = datetime.date.today()
        next_year = today.year + 1
        self._add_solar_schedule(msg, next_year, month, day, hour, minute)

    def add_lunar_schedule(
        self,
        lunar_month,
        lunar_day,
        hour=8,
        minute=3,
        who="someone",
        greeting_words=None,
    ):
        if self.scheduler is None:
            logger.error("Scheduler is not set. Please set_scheduler() first.")
            return

        msg = self.generate_birthday_greeting(who, greeting_words)

        now_lunar_date = self.get_now_lunar_date()
        lunar_date = LunarDate(now_lunar_date.year, lunar_month, lunar_day)
        if lunar_date < LunarDate.today():
            lunar_date = LunarDate(now_lunar_date.year + 1, lunar_month, lunar_day)

        self._add_lunar_schedule(
            msg, lunar_date.year, lunar_month, lunar_day, hour, minute
        )

    def add_solar_schedule(
        self, month, day, hour=8, minute=3, who="someone", greeting_words=None
    ):
        if self.scheduler is None:
            logger.error("Scheduler is not set. Please set_scheduler() first.")
            return

        msg = self.generate_birthday_greeting(who, greeting_words)

        now = datetime.datetime.now()
        solar_date = datetime.date(now.year, month, day)
        if solar_date < now.date():
            solar_date = solar_date.replace(year=now.year + 1)

        self._add_solar_schedule(msg, solar_date.year, month, day, hour, minute)


class LLM(Notice):
    """通用大模型对话类，适配任意 OpenAI 兼容接口

    可直接传入 base_url 与 api_key 即可对话，也可省略后从 [notice] 配置读取：
      llm_base_url / llm_api_key / llm_model

    :param base_url: OpenAI 兼容的服务地址，如 https://api.deepseek.com
    :param api_key: 服务对应的 api key
    :param model: 模型名称，如 deepseek-v4-flash、gpt-4o-mini
    :param system_prompt: 系统提示词，默认 "You are a helpful assistant"
    :param keys_filepath: 当 base_url/api_key/model 未直接传入时，从此文件读取
    """

    def __init__(
        self,
        base_url=None,
        api_key=None,
        model=None,
        system_prompt="You are a helpful assistant",
        keys_filepath="pten_keys.ini",
        **kwargs,
    ):
        super().__init__()
        self.keys = Keys(keys_filepath)

        # 直接传入的参数优先，未传入则回退到 [notice] 配置
        self.base_url = base_url or self._get_notice_key("llm_base_url")
        self.api_key = api_key or self._get_notice_key("llm_api_key")
        self.model = model or self._get_notice_key("llm_model")
        self.system_prompt = system_prompt

        if not self.base_url or not self.api_key or not self.model:
            info = "base_url、api_key、model 不能为空，请直接传入或在 [notice] 中配置llm_base_url / llm_api_key / llm_model"
            raise ValueError(info)

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_notice_key(self, option):
        try:
            return self.keys.get_key("notice", option)
        except (configparser.Error, FileNotFoundError):
            logger.warning(f"Can not find {option} in keys ini file")
            return None

    def get_completion(self, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

        return response.choices[0].message.content


class Deepseek(LLM):
    """DeepSeek 专用便捷类，等价于指向 DeepSeek 的 LLM

    已由更通用的 LLM 类替代，保留以兼容旧代码；建议直接使用 LLM。
    """

    def __init__(self, keys_filepath="pten_keys.ini", **kwargs):
        sk_api_key = Keys(keys_filepath).get_key("notice", "deepseek_api_key")
        super().__init__(
            base_url="https://api.deepseek.com",
            api_key=sk_api_key,
            model="deepseek-v4-flash",
            keys_filepath=keys_filepath,
            **kwargs,
        )


class Weather(Notice):
    def __init__(self, keys_filepath="pten_keys.ini", **kwargs):
        super().__init__()
        self.keys = Keys(keys_filepath)
        self.api_key = self.keys.get_key("notice", "seniverse_api_key")
        self.cities = {}

    def add_city(self, city_name, city_code):
        self.cities[city_name] = city_code

    def get_weather(self, city_code):
        url = f"https://api.seniverse.com/v3/weather/now.json?key={self.api_key}&location={city_code}&language=zh-Hans&unit=c"

        response = requests.get(url)
        weather_json = json.loads(response.text)
        weather = weather_json["results"][0]["now"]

        return weather

    def get_city_weather(self, city_name, city_code):
        weather = self.get_weather(city_code)

        weather_text = weather.get("text")
        weather_temperature = weather.get("temperature")

        weather_str = f"{city_name}: {weather_text},\t 温度: {weather_temperature}度"

        return weather_str

    def report_weather(self):
        if not self.cities:
            logger.warning("No city added. Please add_city() first.")
            return
        weather_str = "今日天气："
        for city_name, city_code in self.cities.items():
            weather_str += "\n" + self.get_city_weather(city_name, city_code)

        self.report_func(weather_str)
