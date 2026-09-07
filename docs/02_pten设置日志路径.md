
# pten : 设置日志路径

pten 的日志一直是「import 即生效、写到哪算哪」——文件名固定为 `pten.log`、跟着进程的工作目录（CWD）走。v0.4.2 起支持自定义日志路径：配置文件里加一行，或代码里调一次 `pten.setup_logging()`。

## 1. 背景：日志散落在各个工作目录里

`import pten` 的瞬间，`src/pten/__init__.py` 就把包内 `logger` 配置好了：一个彩色 console handler，加一个 30MB 轮转的文件 handler。方便是方便，但文件落点长期不可控。

- 文件名硬编码为 `pten.log`，且相对 CWD 解析——在哪个目录起进程，日志就落在哪个目录
- 多个项目共用 pten 时，每个项目目录下都会冒出一个 `pten.log`，日志散落、难以归集
- 定时任务、服务器部署场景更麻烦：工作目录可能不可写，或希望日志统一进 `/var/log` 之类的位置
- v0.4.2引入两种自定义方式：配置文件 `[globals]` 的 `log_path`，以及编程接口 `pten.setup_logging()`

## 2. 基础使用：配置文件里的 log_path

最常用的方式：在 pten 的配置文件 `[globals]` 段加一行 `log_path`，日志路径跟着 `Keys` 走，业务代码零改动。

```ini
[globals]
debug_mode=False
log_path=/var/log/pten/app.log  
; log_path是可选参数，默认 pten.log（相对 CWD）
```

- 生效链路：`Keys` 构造函数会读取 `[globals]` 的 `log_path` 并调用 `setup_logging()`，把文件 handler 切到该路径
- 所有传 `keys_filepath` 的入口类（`BotMsgSender`、`AppMsgSender`、`Contact`、`Doc` 等）构造时都会间接触发，无需每个调用点单独处理
- 路径可相对（相对 CWD）可绝对；跨项目/部署场景建议直接配绝对路径
- 不配置或配置文件里读不到时，回退默认值 `pten.log`（相对 CWD），行为与旧版一致

## 3. 进阶用法：pten.setup_logging() 显式配置

不想动配置文件，或需要在运行时切换日志位置时，直接调 `pten.setup_logging()`。

```python
import pten
pten.setup_logging(r"/var/log/pten/app.log")
```

- 典型场景：轻量脚本不构造 `Keys`；部署框架想统一接管日志位置；长跑进程运行中切到新路径
- 幂等：内部记录当前 handler 实际写入的绝对路径（`_current_log_path`），同一路径重复调用直接返回，不会反复增删 handler
- 与 `Keys` 的相互作用：`Keys` 构造时也会触发 `setup_logging()`——所以用不同配置文件构造多个 `Keys` 时，后构造的 `log_path` 生效（包级 `logger` 只有一个文件 handler）
- `log_path` 传 `None` 则回到默认值 `pten.log`

## 4. 行为细节：回退、幂等与轮转

这套机制有几条刻意设计的边界行为:

- 容错回退：路径不可用（目录建不了、无权限等）时静默回退默认 `pten.log`，保证日志不丢；设计原则是「日志初始化绝不能阻断 `import pten`」，任何异常都不往外抛
- 轮转策略不变：单文件 30MB、保留 3 个备份（`RotatingFileHandler`）
- 切换只动文件 handler：彩色 console 输出始终保留，不受路径切换影响

## 5. 常见问题与技巧

版本迭代留下的行为差异，加上实际使用中容易碰到的点，集中在这里说清:

- **设置了 log_path，CWD 下为什么还有个空的 `pten.log`？** v0.4.2 的实现里 `import pten` 时就用默认路径建了文件 handler（立刻创建空文件），之后才切到配置路径；v0.4.5 给 `RotatingFileHandler` 加了 `delay=True`，文件延迟到首次写入才创建，问题消除
- **日志目录不存在会怎样？** v0.4.2 会回退到默认路径；v0.4.5 起 `_ensure_log_dir` 会自动创建父目录，`logs/app.log` 这类配置直接可用，建不了目录才回退
- **多项目共用一份日志** → 配绝对路径；**各项目各写各的** → 每个配置文件里写各自的路径
- **多进程写同一个日志文件**：`RotatingFileHandler` 在多进程同时轮转时可能冲突（Python logging 的已知限制），多进程部署建议每进程一个日志路径，或交给系统级日志收集
- **日志级别/格式暂不开放配置**：固定 INFO 级别 + 统一格式；有特殊需求可自行拿 `pten.logger` 追加 handler

## 6. 小结

自定义日志路径之后，pten 的日志做到: 位置可控、行为可预期，多项目和部署场景不再满地找 `pten.log`。

- 两种方式：配置文件 `[globals]` 的 `log_path`（推荐，零代码改动）；`pten.setup_logging()`（显式、随时可切）
- 版本注记：v0.4.2 引入该功能；v0.4.5 修复空 `pten.log` 问题并支持自动创建日志目录
- 建议：先在现有 `pten_keys.ini` 加一行 `log_path` 跑通验证，再按需考虑显式调用
