"""Weather（心知天气）天气通知示例。

运行前提：[notice] 配置 seniverse_api_key。
运行方式：python examples/notice/weather.py
"""

from pten.notice import Weather

if __name__ == "__main__":
    weather = Weather()

    # 添加要查询的城市：中文名 + 心知天气的 city_code（拼音或城市ID），可添加多个
    weather.add_city("深圳", "Shenzhen")
    weather.add_city("北京", "Beijing")

    # 查询并输出天气；默认 print 到控制台，
    # 可配合 apscheduler 定时调用（如每天早上 report_weather() 一次）
    weather.report_weather()

    # 把通知改发到企业微信机器人（需 [ww] webhook_key）：
    # from pten.wwmessager import BotMsgSender
    # weather.set_report_func(BotMsgSender().send_text)
    # weather.report_weather()
