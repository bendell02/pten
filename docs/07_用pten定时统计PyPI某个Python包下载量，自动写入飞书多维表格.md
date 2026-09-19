# 用 pten 定时统计 PyPI 某个Python包下载量，自动写入飞书多维表格

把包发布到 PyPI 之后，"今天有多少人下载了"大概是作者最想看的数字。pypistats.org 提供了按包查询的下载量数据（周 / 月 / 日），但每次手动开网页，数据不会自己留痕——想看趋势、做月报，得先把每天的快照存下来。

pten v0.4.13 恰好凑齐了这条链路的全部零件：`PypiStats` 查下载量、`FsBitable` 写多维表格、apscheduler 管定时（它是 pten 的既有依赖，装 pten 时已经自动装好）。这篇就用它们组装一个每天自动跑的小脚本，顺便做一件很"自举"的事——用 pten 统计 pten 自己的下载量。

## 1. 目标与链路

每天中午自动执行一次：

1. 从 pypistats.org 拉 pten 的最近一周、最近一个月、最近 180 天下载量；
2. 写一条记录进飞书多维表格（日期 + 三个指标）；
3. 拉数失败就打日志、跳过本次写入，绝不让脏数据进表。

链路一句话：**pypistats.org → PypiStats（拉数、限流退避）→ FsBitable（本地校验、写记录）→ 飞书多维表格（台账 + 仪表盘）**。

数据落在多维表格而不是日志文件或数据库，是因为它对这条链路有天然优势：多人点开链接就能看，自带仪表盘画趋势，后续还能用飞书的筛选、统计接着加工。

## 2. pten：主页与安装

pten 是一个封装飞书与企业微信 API 的 Python 工具库，覆盖机器人/应用消息、通讯录、文档、回调加解密，以及多维表格读写。三个入口：

- GitHub 主页：<https://github.com/bendell02/pten>
- Gitee 镜像：<https://gitee.com/bendell02/pten>
- PyPI 项目页：<https://pypi.org/project/pten/>

安装（要求 Python 3.8+）：

```bash
pip install -U pten
```

或源码安装：

```bash
git clone https://github.com/bendell02/pten.git
cd pten
pip install -e .
```

安装会自动带上 `apscheduler`、`lunardate`、`openai`、`pycryptodome`、`requests` 几个依赖——其中 requests 和 apscheduler 正是本篇要用的两块拼图。

本篇用到两个能力，均在 v0.4.13 就绪：

| 能力 | 模块 | 说明 |
|---|---|---|
| 下载量查询 | `pten.tools.PypiStats` | 查任意 PyPI 包的周/月/近 180 天下载量，无需任何配置 |
| 多维表格读写 | `pten.fs_bitable.FsBitable` | v0.4.9 起提供增删改查，v0.4.13 补上写入前的本地字段校验 |

## 3. 准备工作

### 3.1 飞书侧：一个能操作多维表格的自建应用

`FsBitable` 走自建应用的 `tenant_access_token` 鉴权：

1. 在[飞书开放平台](https://open.feishu.cn)创建一个企业自建应用，拿到 **App ID** 和 **App Secret**；
2. 开通多维表格权限：`bitable:app`（查看、评论、编辑和管理多维表格）或 `base:app:create`，任一即可；
3. **发布一个版本**，权限才对租户生效；
4. 确保应用是目标多维表格的所有者或协作者——要么把应用加为已有表格的协作者，要么直接用 `FsBitable.create_app` 以应用身份创建（应用天然是所有者）。


### 3.2 配置文件

凭证放在 `pten_keys.ini` 的 `[fs]` 段，这条链路只需要两个键：

```ini
[fs]
app_id=cli_xxxxxxxx
app_secret=xxxxxxxx
```

配置文件按「显式路径 → `PTEN_KEYS_FILE` 环境变量 → 当前目录 `./pten_keys.ini` → `~/.pten/pten_keys.ini`」的顺序查找。token 的获取、缓存（`pten_token.json`，与配置文件同目录）、过期刷新全部自动，代码里不用管。

### 3.3 建一张目标数据表

可以手动新建多维表格，然后把应用加为该多维表格的协作者

或者直接用 `FsBitable` 自己建：

```python
from pten.fs_bitable import FsBitable, FsFieldType

bitable = FsBitable()
app_res = bitable.create_app(name="pten下载量台账")
app_token = app_res["data"]["app"]["app_token"]

table_res = bitable.create_table(
    app_token,
    "每日下载量",
    fields=[
        {"field_name": "日期", "type": FsFieldType.DATETIME},
        {"field_name": "最近一周的下载量", "type": FsFieldType.NUMBER},
        {"field_name": "最近一个月的下载量", "type": FsFieldType.NUMBER},
        {"field_name": "最近180天的下载量", "type": FsFieldType.NUMBER},
    ],
)
table_id = table_res["data"]["table_id"]
print(app_token, table_id)  # 记下来，后面要用
```

在飞书里人工建表也一样，字段名对上即可。`app_token`/`table_id` 也可以从多维表格的 URL 里取：

```
https://xxx.feishu.cn/base/<app_token>?table=<table_id>
```

## 4. 三个零件的组装细节

### 4.1 PypiStats：把限流挡在门外

先看最简单的用法——不需要任何配置（pypistats.org 不要求鉴权），仓库里的 `examples/tools/pypi_stats.py` 可以直接跑：

```bash
python examples/tools/pypi_stats.py pten
```

```python
from pten.tools import PypiStats

stats = PypiStats("pten")
stats.week_downloads()            # 最近一周
stats.month_downloads()           # 最近一月
stats.last_180_days_downloads()   # 最近180天
```

两个工程细节它替你处理了：

- **限流**：pypistats.org 按 IP 全站限流，超限返回 429，且 body 是一段 HTML 而非 JSON——直接 `.json()` 会抛一条不明所以的 `JSONDecodeError`。`PypiStats` 的请求统一走「先查状态码再解析、429/5xx/超时退避重试」的管道；除 429 外的 4xx（如包名拼错的 404）是确定性失败，不会空耗重试。
- **缓存**：周、月下载量同源（`/api/packages/<pkg>/recent`），一次请求的结果缓存 1 小时，两个指标只发一次请求；180 天口径来自 `/overall` 的日明细求和。

定时任务是长驻进程里的 cron，偶发限流等得起，所以把重试拉满：

```python
stats = PypiStats(
    package,
    retries=10,  # 含首次请求在内最多尝试 10 次
    # 退避从 30 秒起逐次翻倍，覆盖全部 9 次重试
    backoff=tuple(30 * 2**i for i in range(9)),
)
```

30 → 60 → 120 → … → 7680 秒的指数退避，最坏情况累计能等 4 个多小时——对每天跑一次的任务完全无所谓，却几乎必然熬过限流窗口（实测几分钟内恢复）。

拿不到数据时 `PypiStats` 抛 `requests.RequestException` / `ValueError`。定时任务里要兜住它：打一条干净的 warning、跳过本次写入——宁可这天缺一条记录，也不让 traceback 吓到人、更不能把 None 写进表：

```python
try:
    stats = PypiStats(package, retries=10, backoff=tuple(30 * 2**i for i in range(9)))
    downloads_week = stats.week_downloads()
    downloads_month = stats.month_downloads()
    downloads_180_days = stats.last_180_days_downloads()
except (requests.RequestException, ValueError) as exc:
    logger.warning(f"获取 {package} 下载量失败（{exc}），本次跳过记录写入")
    return
```

一个数据质量注脚：pypistats 的 overall 明细可能缺天，有数据的天数不足 180 时，「最近180天」的总和会偏小，与历史记录不可比——看趋势时心里有数即可。

### 4.2 FsBitable：写入前先本地校验

待写的数据是一个普通 dict，键为字段名：

```python
import datetime
import time

fields = {
    # 日期字段要是毫秒时间戳格式
    "日期": int(time.mktime(datetime.date.today().timetuple()) * 1000),
    "最近180天的下载量": downloads_180_days,
    "最近一个月的下载量": downloads_month,
    "最近一周的下载量": downloads_week,
}
```

飞书的日期字段要求**毫秒时间戳**，传字符串会被服务端拒绝。pten v0.4.13 提供了一道本地预检 `validate_record_fields`：拉取数据表的字段清单后在本地比对，未知字段、只读/系统字段、数字/日期/复选框等标量字段的取值形状不对，都会在**发出写请求之前**被拦下——错误信息直指问题字段，比等服务端吐 4xx 再猜原因省事得多：

```python
bitable.validate_record_fields(app_token, table_id, fields=fields)
```

校验过了再写，返回值里带 `record_id`：

```python
record_res = bitable.create_record(app_token, table_id, fields=fields)
record_id = record_res["data"]["record"]["record_id"]
```

### 4.3 apscheduler：每天 12:30 跑一次

```python
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()
scheduler.add_job(stat_package_downloads, "cron", hour=12, minute=30)

try:
    logger.info("scheduler is running...")
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    pass
```

`cron` 触发器按机器本地时间执行；每天写一行，攒一个月就有 30 行，趋势自然浮现。

## 5. 完整脚本

组装完毕：

- 脚本命名为 `stat_package_downloads.py`
- 首跑（脚本顶部 `APP_TOKEN`/`TABLE_ID` 未填）会自动创建一个多维表格和数据表，把两个 ID 打印出来；
- 把打印的两行常量填回脚本顶部，重新运行；
- 在机器上执行 `python stat_package_downloads.py` 就会每天自动统计并写入多维表格记录了

```python
"""定时统计 PyPI 包下载量并写入飞书多维表格示例（数据来自 pypistats.org）。

每天定时（12:30）统计一次包的周 / 月 / 近180天下载量，写入多维表格一条记录；
包名取命令行参数，缺省 pten。拉数失败（限流/网络）时跳过本次写入。

运行前提：[fs] 配置 app_id、app_secret。
注意：本例为常驻定时任务，Ctrl+C 退出；首跑（脚本顶部 APP_TOKEN / TABLE_ID 未填）
会自动创建一个多维表格和数据表，把两个 ID 打印出来，填回脚本顶部常量后重新运行，
即开始每日统计。
运行方式：python stat_package_downloads.py [包名]
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
    table_res = bitable.create_table(app_token, "下载量统计", fields=TABLE_FIELDS)
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
```

一点说明：日志直接用 pten 自带的 `logger`——导入即用，可改成自己的或者直接用print。

## 6. 跑起来之后

- 表里每天一行，日期 + 三个指标；给「最近一周的下载量」列在多维表格仪表盘里加个折线图，下载趋势一目了然；
- 表是多人协作的：把多维表格链接发给协作者，大家都能看；
- 换个包照用：`python stat_package_downloads.py requests`；
- 再进一步，配 `FsAppMsgSender` 给下载量做日报卡片——台账与通知一条链路，且可与 `FsBitable` 共享同一个 `Keys` 实例（配置和 token 缓存都只落一份）：

```python
from pten.fs_messager import FsAppMsgSender

sender = FsAppMsgSender(keys=bitable.keys)
sender.send_card(title="pten 下载量日报", content=f"本周 {downloads_week} 次", template="green")
```

## 7. 小结

- 三个零件各管一段：`PypiStats` 把限流、退避、缓存这些脏活挡掉，`FsBitable` 负责写入前的本地校验与服务端交互，apscheduler 负责定时；
- 全部能力出自 `pip install -U pten`（v0.4.13+，Python 3.8+）；
- 这套「定时拉数 → 本地校验 → 写多维表格」的骨架不限于下载量：CI 构建耗时、告警计数、每日天气……凡是能变成一行结构化数据的指标，都能照抄。
