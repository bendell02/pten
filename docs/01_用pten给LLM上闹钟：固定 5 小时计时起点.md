
# 用 pten 给 LLM 上闹钟：固定 5 小时计时起点

很多 LLM 套餐按 5 小时滚动限额计费，计时从第一次调用那一刻起算——集中用一下就见底，然后干等。这篇记一个用 pten 库做定时轻量调用的小脚本：在固定时间点先打一次轻量调用，把 5 小时计时的起点钉住，让等待变成可预期的。

## 1. 当前计时现象
这个限额让人抓狂的关键不在"用了多少"，而在"5 小时从什么时候开始算"。
- 很多模型套餐按"5 小时滚动窗口"限额，计时从第一次调用 LLM 那一刻起算，不是整点
- 这意味着起点跟着你走：9 点开干窗口就 9 点起算，下午才用就下午起算——完全不可控
- 集中使用时窗口被一次耗尽，接下来要等满 5 小时才能恢复
- 结果：想用时用不了、不想用时限额空着，等待的起点和时长都没法预期

## 2. 解决方法
计时起点本不可控，但它由"第一次调用"决定——因此在固定时刻主动发起第一次轻量调用，就能把起点钉住：窗口的刷新时刻从"你刚开干的那一刻"挪到"可预期的固定时间"。
- 核心想法：每天在固定时间点做一次轻量调用，主动设定 5 小时计时的起点
- 选 7:00 / 12:10 / 17:20 三个时间点，把一天切成几段可预期的窗口
- 用 pten 做这次轻量调用：它本是个企业微信 / 飞书 API 工具库，`notice` 模块顺带封装了 OpenAI 兼容的 LLM 调用——开销小、易脚本化，适合做"保活探针"（见 3.1）
- 为什么选 pten：它把 OpenAI 兼容的 LLM 调用、配置文件读 key、（可选）企业微信 / 飞书推送打包好了；对这套脚本一个库就齐活，比单写 curl 或额外拉官方 SDK 省事
- 边界：这个方法治的是"计时起点不可控"，不是"用量超限"——某段窗口用量远超限额时它救不了
- 适用前提：本方案只对"起点随首次调用、固定 5 小时块"型限流有效。若你的服务商是滑动窗口（任意时刻回看过去 5h、本无"起点"概念）或"最后一次调用后满 5h 才重置"，钉桩要么无意义、要么会落进仍在生效的旧窗口——先按服务商规则核对再上

## 3. 具体步骤
思路落成可长期跑的服务，分装库、写脚本、交给 systemd 托管三步。

### 3.1 pten 安装
pten 原本是个方便快捷使用企业微信和飞书 API 的 Python 工具库，它的 `notice` 模块封装了 LLM 调用——这次方案就是用它来发那次轻量调用。
- 安装：`pip install pten`
- 核心类 `LLM`：通用的 OpenAI 兼容大模型对话类，传入 `base_url`、`api_key`、`model` 即可对话，适配 DeepSeek、OpenAI 等不同模型
- 通知内容可以打印，也可以配置发送到企业微信或飞书，详见 [pten 文档](https://gitee.com/bendell02/pten/blob/master/README.md)
- 最小调用示例（跑通它也就顺便验证了安装）：

```python
from pten.notice import LLM

# 直接传参即可对话，适配任意 OpenAI 兼容服务
llm = LLM(base_url="https://api.deepseek.com", api_key="sk-xxx", model="deepseek-v4-flash")
content = llm.get_completion("简略介绍一下牛顿")
```

- 鉴权（两种方式）：
  - 直接传参：见上例 `LLM(base_url=..., api_key=..., model=...)`
  - 配置文件：把 `llm_base_url`、`llm_api_key`、`llm_model` 写进配置文件的 `[notice]` 区，即可 `LLM()` 省参读取；默认配置文件 `pten_keys.ini`，换文件用 `keys_filepath=` 传入

### 3.2 定时调用的脚本
以下脚本 `schedule_llm.py` 用 pten 的 `LLM` + APScheduler 的 `BlockingScheduler` 实现每天定时调用——脚本自身常驻、内部用 cron 触发器在指定时刻调 `get_completion`，这是个长驻进程，不是"被定时拉起一次就退出"的脚本。
- 时间点与提示词集中在文件顶部，改这里即可：`SCHEDULE_TIMES = [(7, 0), (12, 10), (17, 20)]`、`PROMPT = "你好"`
- 多 LLM 并发：每个 LLM 各自从对应 `pten_keys*.ini` 读配置，同一时刻并发调用（每个 LLM × 每个时刻 = 一个独立 job），`LLM_CONFIGS` 里加一项即可扩
- 输出通道：`set_report_func` 把回复导向带时间戳和名称的 `print`，以后可换成企业微信 / 飞书推送
- 钉桩失败可见：`get_completion` 抛异常时 APScheduler 会吞掉并记 journal、调度器继续转，但那次窗口起点其实没钉住——脚本在 `run_once` 里 catch 异常并走同一 `report` 通道告警，避免静默失效
- 完整脚本：

```python
"""每天定时调用一次 LLM(7:00 / 12:10 / 17:20)。

用 pten 的 LLM + APScheduler(BlockingScheduler) 实现:
  - 多个 LLM 各自从对应的 pten_keys*.ini 读取 base_url/api_key/model,
    同一时刻并发调用(每个 LLM × 每个时刻 = 一个独立 job);
  - set_report_func 把回复导向带时间戳和名称的 print(以后可换企业微信/飞书推送);
  - 脚本持有 BlockingScheduler,用 add_job 的 cron 触发器在指定时刻调用 get_completion。

常驻运行:
    nohup python3 schedule_llm.py >> llm_schedule.log 2>&1 &
"""

from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from pten.notice import LLM


# keys 文件
KEY_FILEPATH_1 = "your_pten_keys_1.ini"
KEY_FILEPATH_2 = "your_pten_keys_2.ini"

# 每天调用的时刻(24h, 本地时区)与提示词,改这里即可
SCHEDULE_TIMES = [(7, 0), (12, 10), (17, 20)]
PROMPT = "你好"
SYSTEM_PROMPT = "You are a helpful assistant from Claude Code"

# 要定时调用的 LLM:(名称, keys 文件)。名称用于区分日志和 job id;
# 新增一个 LLM 时,在上面定义它的 KEY_*_FILEPATH,然后往这里加一项即可。
LLM_CONFIGS = [
    ("llm_1", KEY_FILEPATH_1),
    ("llm_2", KEY_FILEPATH_2),
]


def make_report(name: str):
    """生成带 LLM 名称的输出通道;以后可换成企业微信/飞书推送。"""

    def report(text: str) -> None:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{name}] {text}", flush=True)

    return report


def make_run_once(llm: LLM):
    """为指定 LLM 生成单次调用闭包(get_completion -> report_text)。
    用工厂而非循环内直接定义,避免闭包共享循环变量。
    钉桩调用失败时(网络/限流/key 失效),APScheduler 会吞掉异常、调度器继续转,
    catch住并走 report 通道告警,让失败可见。"""

    def run_once() -> None:
        try:
            llm.report_text(llm.get_completion(PROMPT))
        except Exception as e:  # 钉桩探针:失败不能静默吞
            llm.report_text(f"[钉桩失败] {type(e).__name__}: {e}")

    return run_once


def main() -> None:
    sched = BlockingScheduler()

    for name, keys_filepath in LLM_CONFIGS:
        llm = LLM(system_prompt=SYSTEM_PROMPT, keys_filepath=keys_filepath)
        llm.set_report_func(make_report(name))

        run_once = make_run_once(llm)
        for hour, minute in SCHEDULE_TIMES:
            sched.add_job(
                run_once,
                "cron",
                hour=hour,
                minute=minute,
                id=f"{name}_{hour:02d}{minute:02d}",
                misfire_grace_time=300,
            )

    times_str = ", ".join(f"{h:02d}:{m:02d}" for h, m in SCHEDULE_TIMES)
    names_str = ", ".join(name for name, _ in LLM_CONFIGS)
    print(
        f"已就绪,每天 {times_str} 调用一次 LLM({names_str}, prompt={PROMPT!r})。Ctrl+C 退出。",
        flush=True,
    )
    for job in sched.get_jobs():
        # APScheduler 3.x 在 start() 前 Job.next_run_time 尚未实例化,
        # 改用 trigger 计算下一次触发时间
        nrt = job.trigger.get_next_fire_time(None, datetime.now())
        print(f"  {job.id} -> 下次触发: {nrt:%Y-%m-%d %H:%M:%S}", flush=True)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
```

- systemd 接管前，可先用脚本 docstring 里的 `nohup` 方式手动常驻跑一遍验证

### 3.3 做成 systemd 服务
脚本自己是长驻进程（APScheduler 在内部管时间），所以 systemd 只当一个"把它跑起来、崩了重启"的守护层——配一个 service 单元即可，不需要 timer 单元、也不用 OnCalendar（时间点仍在脚本里改 `SCHEDULE_TIMES`）。
- 步骤一：建单元文件并启用（整段粘贴，需 sudo）。unit 里的 `User` / `Group` / `WorkingDirectory` / `ExecStart` 路径都换成你自己的：

```bash
sudo tee /etc/systemd/system/llm-schedule.service >/dev/null <<'UNIT'
[Unit]
Description=pten LLM daily scheduler (7:00/12:10/17:20)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<你的用户名>
Group=<你的用户组>
WorkingDirectory=/<你的工作目录>/
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /<脚本所在绝对路径>/schedule_llm.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
```
然后
```shell
sudo systemctl daemon-reload
sudo systemctl enable --now llm-schedule.service
```

- 步骤二：验证

```bash
systemctl status llm-schedule.service         # 应为 active(running)
journalctl -u llm-schedule -n 20 --no-pager   # 看到「已就绪,每天...」+ 每个 job 的下次触发时间
journalctl -u llm-schedule -f                 # 实时跟;到点会出 [llm_1] / [llm_2] 的回复
```

- 步骤三：日常操作
  - 改了脚本（`SCHEDULE_TIMES` / `PROMPT` / `LLM_CONFIGS` 等）→ 只需 restart，不用 daemon-reload：`sudo systemctl restart llm-schedule.service`
  - 改了 unit 文件本身 → reload 再 restart：`sudo systemctl daemon-reload && sudo systemctl restart llm-schedule.service`
  - 停服务 / 查日志：`sudo systemctl stop llm-schedule.service`、`journalctl -u llm-schedule`
- 日志：脚本 stdout / stderr 默认进 journald，用 `journalctl` 看；`Environment=PYTHONUNBUFFERED=1` 让 print 不被缓冲、实时落日志

## 4. 小结
限额没变，变的只是计时起点。
- 本质：把 5 小时计时的起点从"被动跟着第一次调用"变成"主动钉在固定时间"
- pten 在这里扮演"保活探针"，开销小、够用
- 效果：等待从"随机 0–5 小时"变成"最多等到下一个固定时间点"
- 适合：限额按滚动窗口算、且使用时间相对固定的人
