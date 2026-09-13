"""Birthday 生日提醒示例（农历/阳历，apscheduler 定时触发）。

运行前提：无需配置（默认 print 到控制台；接机器人通知则需对应发送方的配置）。
注意：BlockingScheduler 会一直阻塞进程（适合部署在常驻服务里），本地体验 Ctrl+C 退出。
     提醒触发后会自动排下一年的提醒；今年的日期已过时也会自动排到明年。
运行方式：python examples/notice/birthday.py
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from pten.notice import Birthday

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    birthday = Birthday()

    # 提醒由 scheduler 触发，先注入；不设置时 add_*_schedule 只会报错返回
    birthday.set_scheduler(scheduler)

    # 默认打印到控制台；想发到企业微信机器人（需 [ww] webhook_key）：
    # from pten.wwmessager import BotMsgSender
    # birthday.set_report_func(BotMsgSender().send_text)

    # 农历生日提醒（自动处理闰月），缺省在当天 08:03 提醒（hour/minute 参数可改）
    birthday.add_lunar_schedule(3, 15, who="玛丽")
    # 可用 greeting_words 定制提醒语
    birthday.add_lunar_schedule(
        3, 15, who="玛丽", greeting_words="玛丽来到地球纪念日，生快！"
    )
    # 阳历生日提醒
    birthday.add_solar_schedule(1, 12, who="玛莉亚")

    # 阻塞运行，Ctrl+C 退出
    scheduler.start()
