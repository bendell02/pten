# pten 配置文件查找顺序：环境变量、当前目录与用户主目录

pten v0.4.11 之前，配置文件 `pten_keys.ini` 的路径写死成当前目录，脚本换个目录跑就找不到配置、token 缓存也散落各处。v0.4.11 给 `Keys` 加了一条查找链——缺省时按「环境变量 → 当前目录 → 用户主目录」顺序找，配合显式传入的路径，覆盖从本地调试到容器/CI 的多种部署场景。

## 1. 简介

旧版 pten 的所有公开类（`BotMsgSender`、`AppMsgSender`、`FsAppMsgSender`、`LLM` 等）默认 `keys_filepath="pten_keys.ini"`，即相对当前工作目录解析，token 缓存 `pten_token.json` 也固定落在 CWD。换个目录运行脚本就要重新放一份配置，也没法给一台机器配一份全局配置。v0.4.11 把默认值改成 `keys_filepath=None`，由 `Keys._resolve_keys_filepath` 按优先级查找。
- 查找链（优先级从高到低）：显式传入路径 → 环境变量 `PTEN_KEYS_FILE` → 当前目录 `./pten_keys.ini` → 用户主目录 `~/.pten/pten_keys.ini`
- 前两级「严格」：指向的文件不存在时直接报错，不回退；后两级「探测」：不存在就继续往下找
- token 缓存 `pten_token.json` 跟随最终解析出的配置文件同目录，全局配置（`~/.pten`）时 token 不再散落到 CWD
- 所有公开类的 `keys_filepath` 默认值从 `"pten_keys.ini"` 改为 `None`，触发查找链；显式传路径的行为完全不变，向后兼容

## 2. 安装与准备

本功能自 v0.4.11 起发布，升级到该版本即可使用。pten 主页在 GitHub（含 Gitee 镜像），要求 Python 3.8+。
- pten 主页：[GitHub](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)）
- 安装/升级：`pip install -U pten`（>= 0.4.11，Python 3.8+）；或 clone 仓库后源码安装 `pip install -e .`
- 准备一个最小配置文件，比如只用企业微信机器人，`pten_keys.ini` 里放：
```ini
[ww]
webhook_key=7ande764-52a4-43d7-a252-05e8abcdb863
```
- 这份文件放哪都行——当前目录、`~/.pten/`，或用环境变量指向它，下面分别讲

## 3. 基础使用

什么都不传，`Keys` 就会按查找链找配置；最先命中的是当前目录的 `pten_keys.ini`，没有再去找 `~/.pten/pten_keys.ini`。
- 最省事：把 `pten_keys.ini` 放在当前目录，`BotMsgSender()` 不传任何路径即可：
```python
from pten.wwmessager import BotMsgSender

bot = BotMsgSender()  # 缺省触发查找链，命中 ./pten_keys.ini
bot.send_text("hello world")
```
- 当前目录没有配置时，自动回退到用户主目录 `~/.pten/pten_keys.ini`——适合「一台机器配一份，到处跑」
- 四级优先级与严格/探测的区别：

| 优先级 | 来源 | 文件缺失时 |
|---|---|---|
| 1 | 显式传入 `keys_filepath` | 直接报错，不回退 |
| 2 | 环境变量 `PTEN_KEYS_FILE` | 直接报错，不回退 |
| 3 | 当前目录 `./pten_keys.ini` | 继续探测下一级 |
| 4 | 主目录 `~/.pten/pten_keys.ini` | 查找链结束：`Keys` 持有 `./pten_keys.ini` 并告警，取 key 时抛错（旧行为） |

- token 缓存自动落在配置文件同目录：用 `~/.pten/pten_keys.ini` 时，`pten_token.json` 也写到 `~/.pten/`，不再污染各个运行目录

## 4. 进阶用法

除了「放当前目录」和「放主目录」，查找链还支持环境变量注入和显式路径，适配 CI、容器、多项目共用一份配置等场景。

### 4.1 用环境变量指定配置文件

不改代码，靠 `PTEN_KEYS_FILE` 环境变量切换配置文件——CI 流水线、容器里特别好用：
```bash
export PTEN_KEYS_FILE=/opt/secrets/pten_keys.ini
python your_script.py
```
```python
from pten.keys import Keys

keys = Keys()  # 命中环境变量指向的文件
```
- 环境变量里的 `~` 会展开为用户主目录：`PTEN_KEYS_FILE=~/.pten/pten_keys.ini`
- 环境变量指向的文件不存在时**严格报错**（取 key 时抛 `FileNotFoundError`），不偷偷回退到当前目录——避免「以为用了线上配置，其实用了本地配置」；文件存在但缺对应节/键（如没有 `[fs]` 节）时则抛 `configparser.Error("KeyConfigError")`

### 4.2 显式传入路径

优先级最高，盖过环境变量；适合一个脚本里同时用多份配置：
```python
from pten.wwmessager import BotMsgSender

prod = BotMsgSender("/opt/secrets/pten_keys_prod.ini")
test = BotMsgSender("./pten_keys_test.ini")
```
- 显式路径同样支持 `~` 展开：`Keys("~/.pten/pten_keys.ini")`
- 显式路径文件缺失时也**严格报错不回退**

### 4.3 token 缓存跟随配置文件

`pten_token.json` 永远与解析出的 keys 文件同目录——无论配置来自哪一级：
```python
from pten.keys import Keys

keys = Keys()  # 命中 ~/.pten/pten_keys.ini
print(keys.TOKEN_PATH)  # ~/.pten/pten_token.json，而非 CWD 下
```
- 好处：用 `~/.pten` 做全局配置时，token 缓存集中在一处，不会在每个运行目录各留一份
- token 缓存目录不可写时（如只读挂载）仅告警不抛异常，内存缓存照常生效

### 4.4 跨模块共享 Keys 实例

多个模块共用一份配置和 token 缓存时，构造一个 `Keys` 注入即可，避免重复读文件、重复取 token：
```python
from pten.keys import Keys
from pten.wwmessager import AppMsgSender
from pten.notice import LLM

keys = Keys()  # 一次查找，一次缓存
app = AppMsgSender(keys=keys)
llm = LLM(keys=keys)
```

## 5. 注意事项与说明

- **显式路径/环境变量文件不存在为什么直接报错？** 前两级是「严格」匹配——你明确指定了它，就该用它；偷偷回退到别的配置反而危险（可能用错 corpid 发错消息）。报错形式分两种：文件本身不存在时，取 key 抛 `FileNotFoundError`；文件存在但缺对应节/键（如没有 `[fs]` 节）时，抛 `configparser.Error("KeyConfigError")`。
- **当前目录和主目录都没有会怎样？** 回落到 `./pten_keys.ini` 并告警，保持 v0.4.11 之前的旧行为（初始化仅告警，真正取 key 时才抛 `FileNotFoundError`），旧代码不受影响。
- **`PTEN_KEYS_FILE` 设成空字符串算不算指定？** 不算——空串视为未设置，继续探测当前目录。
- **容器里没有主目录会报错吗？** 不会。`Path.home()` 在无 passwd 条目的容器 UID 下会抛 `RuntimeError`，查找链捕获后跳过主目录这一级，只要当前目录有配置就正常命中。
- **旧代码传 `BotMsgSender("pten_keys.ini")` 还能用吗？** 能。显式传 `"pten_keys.ini"` 等价于优先级第 1 级，行为与旧版一致，无需改动。

## 6. 小结

v0.4.11 的查找链让配置文件不再绑死当前目录：缺省按「显式路径 → `PTEN_KEYS_FILE` → `./pten_keys.ini` → `~/.pten/pten_keys.ini`」找，前两级严格、后两级探测，token 缓存跟随配置同目录。
- 使用建议：本地调试放当前目录；一台机器多处复用放 `~/.pten`；CI/容器用 `PTEN_KEYS_FILE` 注入；一脚本多配置用显式路径
- 更多细节见 [pten 主页](https://github.com/bendell02/pten)（[Gitee 镜像](https://gitee.com/bendell02/pten)）的 README 与 `Keys` 类 docstring
