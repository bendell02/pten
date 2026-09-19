"""定时统计 PyPI 包下载量并写入飞书多维表格示例（数据来自 pypistats.org）。

每天定时（12:30）统计一次包的周 / 月 / 近180天下载量，写入多维表格一条记录；
包名取命令行参数，缺省 pten。拉数失败（限流/网络）时跳过本次写入。

运行前提：[fs] 配置 app_id、app_secret。
注意：本例为常驻定时任务，Ctrl+C 退出；首跑（脚本顶部 APP_TOKEN / TABLE_ID 未填）
会自动创建一个多维表格和数据表，把两个 ID 打印出来，填回脚本顶部常量后重新运行，
即开始每日统计。
运行方式：python examples/tools/stat_package_downloads.py [包名]
"""

import datetime
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler
import requests

from pten import logger
from pten.fs_bitable import FsBitable, FsFieldType
from pten.tools import PypiStats

# 替换成你自己的多维表格 app_token / table_id；保持 None 时首跑自动创建并提示填回
APP_TOKEN = None
TABLE_ID = None

# 数据表字段结构（首跑建表时使用）：日期 + 三个口径的下载量
TABLE_FIELDS = [
    {"field_name": "日期", "type": FsFieldType.DATETIME},
    {"field_name": "最近一周的下载量", "type": FsFieldType.NUMBER},
    {"field_name": "最近一个月的下载量", "type": FsFieldType.NUMBER},
    {"field_name": "最近180天的下载量", "type": FsFieldType.NUMBER},
]


def resolve_table(bitable):
    """返回 (app_token, table_id)；常量未填（首跑）时自动建表，打印 ID 提示填回后退出。"""
    if APP_TOKEN and TABLE_ID:
        return APP_TOKEN, TABLE_ID
    app_res = bitable.create_app(name="包下载量台账")
    app_token = app_res["data"]["app"]["app_token"]
    table_res = bitable.create_table(app_token, "每日下载量", fields=TABLE_FIELDS)
    table_id = table_res["data"]["table_id"]
    print(f"已创建多维表格：{app_res['data']['app']['url']}")
    print("把下面两行填回脚本顶部常量后重新运行，即可开始每日统计：")
    print(f'APP_TOKEN = "{app_token}"')
    print(f'TABLE_ID = "{table_id}"')
    sys.exit(0)


def main():
    bitable = FsBitable()
    # 首跑自举：常量未填时建表并退出；已填时直接拿到 (app_token, table_id)
    app_token, table_id = resolve_table(bitable)

    def stat_package_downloads():
        """拉取一次下载量并写入飞书多维表格；失败时跳过本次写入。"""
        package = sys.argv[1] if len(sys.argv) > 1 else "pten"
        # PypiStats 拿不到数据时抛 requests.RequestException / ValueError，
        # 在任务里兜住：打干净提示、跳过本次写入，
        # 避免抛 traceback 或把 None/脏数据写进多维表格。
        try:
            stats = PypiStats(
                package,
                retries=10,
                # 退避从 30 秒起逐次翻倍，覆盖全部 9 次重试
                backoff=tuple(30 * 2**i for i in range(9)),
            )
            downloads_week = stats.week_downloads()
            downloads_month = stats.month_downloads()
            downloads_180_days = stats.last_180_days_downloads()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(f"获取 {package} 下载量失败（{exc}），本次跳过记录写入")
            return

        print(f"包名: {package}")
        print(f"最近一周: {downloads_week}")
        print(f"最近一个月: {downloads_month}")
        print(f"最近180天下载量: {downloads_180_days}")

        fields = {
            # 日期字段要是毫秒时间戳格式
            "日期": int(time.mktime(datetime.date.today().timetuple()) * 1000),  # noqa: DTZ011
            "最近180天的下载量": downloads_180_days,
            "最近一个月的下载量": downloads_month,
            "最近一周的下载量": downloads_week,
        }

        # 写入前本地预检：未知字段 / 只读字段 / 标量取值形状不对，在本地被拦下
        bitable.validate_record_fields(app_token, table_id, fields=fields)

        # 新增一条记录
        record_res = bitable.create_record(app_token, table_id, fields=fields)
        record_id = record_res["data"]["record"]["record_id"]
        print(f"record_id: {record_id}")

    # 每天执行一次下载量统计
    scheduler = BlockingScheduler()
    scheduler.add_job(stat_package_downloads, "cron", hour=12, minute=30)
    try:
        logger.info("scheduler is running...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
