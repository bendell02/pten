# 用 pten 调用 TypeSafe AI 的 jev 模型：一次调用拿到结构化决策

pten v0.4.18 给 `pten.tools` 子包新增了一个 `Jev` 类，封装了 TypeSafe AI 的 **jev** 模型。和 `LLM` 那种「给一句话、回一段话」的对话模型不同，jev 走的是 TypeSafe 的 **System One API**：你交一段上下文（state）和一组结构化问题，它直接返回代码能用的类型化答案——不用再让 LLM 吐 JSON、也不用自己写解析和容错。这篇博客介绍它的用法。

## 1. jev 是什么：给「让模型出判断」这件事上类型

很多实际任务不是要模型「写作」，而是要它「做判断」：这条工单紧急吗？该转给哪个组？客户多愤怒？传统做法是让 LLM 返回 JSON，然后自己解析——但模型偶尔漏字段、偶尔吐个 `true` 字符串、有时候还顺手加段寒暄，容错代码写起来很烦。

jev 把这件事收进 API 本身。一次 `ask` 调用里，你可以同时问多个问题，每个问题声明成下面三种之一，答案的类型在调用前就定死：

| 问题类型 | 含义 | 答案形态 |
| --- | --- | --- |
| `Noul` | 是非判断（是否成立） | `float`，0~1 的概率 |
| `Choice` | 单选（从候选项里选一个） | `str`，命中的候选项名 |
| `Score` | 按等级打分 | `float`，各等级概率加权的期望分，可能落在等级之间（如 `1.7`），需 `round()` 后再当索引用 |

这三类来自 `typesafe_sdk`，pten 已经从 `pten.tools.jev` 重新导出，直接 `from pten.tools.jev import Noul, Choice, Score` 就能用。

## 2. 准备：安装与版本

- 需要 pten **v0.4.18 及以上**。一条命令装好：

```bash
pip install pten
```

- 也可源码安装：克隆仓库后 `pip install -e .`。`typesafe-sdk` 已写进 `setup.py` 的依赖，会随 pten 自动装上。
- 需要 Python ≥ 3.10。
- pten 主页：[GitHub](https://github.com/bendell02/pten) ｜ [Gitee](https://gitee.com/bendell02/pten)

## 3. 配置 api_key

`Jev` 只要求一样东西——**api_key**。它按下面的顺序找，找到即停：

1. 构造参数 `api_key=...`
2. 配置文件 `[jev]` 段的 `api_key`
3. 环境变量 `TYPESAFE_API_KEY`

三者都没有时直接抛 `ValueError`，并把三种途径连同配置文件是否存在一起写进报错信息，照着补就行。

`base_url` 和 `model` 都可以省略：省略时 `Jev` 传 `None` 给 SDK，由 SDK 用默认值（`https://api.typesafe.ai` / `jev-latest`）。配置文件照着仓库里的 `pten_keys_example.ini` 抄改即可：

```ini
[jev]
;TypeSafe AI 的 jev 模型；api_key 三选一：本段 / 构造参数 / TYPESAFE_API_KEY 环境变量
;base_url/model/proxy 均可省略，省略时 base_url/model 用 SDK 默认值（api.typesafe.ai / jev-latest）
api_key=apikey_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
;base_url=https://api.typesafe.ai
;model=jev-latest
```

配置文件还是走 pten 一贯的查找链：`keys_filepath` 参数显式指定 → `PTEN_KEYS_FILE` 环境变量 → 当前目录的 `pten_keys.ini` → 用户主目录 `~/.pten/pten_keys.ini`（前两级严格、后两级探测）。`[jev]` 段可以和 `[ww]`/`[fs]`/`[notice]` 等段并存于同一个 `pten_keys.ini`，密钥不进代码、不进版本库（`pten_keys.ini` 已 gitignore）。

## 4. 最小示例：给客服工单分流

一个最能体现 jev 价值的场景——拿到一条客服工单，同时问三个问题：是否紧急、转给哪个组、客户愤怒程度。三种类型各占一个，一次调用全答完。

```python
from pten.tools.jev import Choice, Jev, Noul, Score

# state：待判断内容（此处为一条客服工单，也可以是 dict 等结构）
ticket = "Hi, I've been trying to connect my Stripe account for 3 days and the integration keeps failing. I'm losing sales. Please help ASAP."

# questions：一组结构化问题，键为自定义问题名
questions = {
    "is_urgent": Noul(
        instructions="The message conveys urgency or time-sensitivity",
    ),
    "department": Choice(
        instructions="Which team should handle this",
        criteria={
            "billing": "Payment or subscription issues",
            "technical": "Bugs or integration problems",
            "sales": "Pricing or account questions",
        },
    ),
    "frustration": Score(
        instructions="How frustrated the customer appears",
        criteria=[
            "Calm, just stating facts",
            "Frustrated but civil",
            "Very angry, strong language",
        ],
    ),
}

# 配置缺省时从 pten_keys.ini 的 [jev] 段读取
with Jev() as jev:
    response = jev.ask(ticket, questions)

    # 答案按问题名取，类型分别为 float(0~1 概率) / str / float
    print("is_urgent:", response.answers["is_urgent"].noul)
    print("department:", response.answers["department"].choice)
    print("frustration:", response.answers["frustration"].score)
```

结果输出为
```
is_urgent: 0.99
department: technical
frustration: 1.0
```

（`frustration` 这里恰好收敛到等级 `1`；它是概率加权的期望分，也可能返回 `1.7` 这类落在等级之间的值，按索引用前先 `round()`。）

几个要点：

- `Jev` 实现了上下文管理器，`with Jev() as jev:` 退出时自动关闭底层客户端（连带其 httpx 连接）；也可手动 `jev.close()`。
- `ask` 的 `state` 可以是 `str`，也可以是 JSON 兼容的 `dict`/`list`——结构化输入直接传，不必先序列化成字符串。
- 答案取值固定走 `.noul` / `.choice` / `.score` 三个属性，和声明问题时的类型一一对应，类型确定、不用猜。
- 每次调用 pten 都会在日志里记一条 `jev ask: model=..., state=..., questions=[...]`（state 经 `brief_for_log` 压缩，不会刷屏），方便排查。

这份示例就是仓库里的 `examples/tools/jev.py`，`python examples/tools/jev.py` 可直接跑。

## 5. 进阶：代理与参数覆盖

**代理。** 部分区域无法直连 `typesafe.ai`。`Jev` 支持配代理，解析顺序和其它配置项一致：

> 显式 `proxy` 参数 → `[jev]` 段 `proxy` → 全局 `[proxies]` 段（优先 `https` 键，缺则回落 `http` 键）

```ini
;无法直连 typesafe.ai 的区域配代理；缺省回落全局 [proxies] 段
;proxy=http://xxx:xxx@xxx.xxx.xxx.xxx:8888
```

解析出代理时，`Jev` 会建一个 `httpx2.Client(proxy=...)` 注入 SDK；都未配置时不干预 SDK 默认客户端（此时 httpx 仍会读 `HTTP(S)_PROXY` 环境变量）。注意它没有复用 `Keys.get_proxies()`——后者要求 http/https 两键齐全、任一缺失即返回 `None`，表达不了「只配一个键」的回落，所以这里单独处理。

**参数覆盖。** 和 pten 其它模块一样，显式传参永远盖过配置文件，方便临时换字段而不动 ini：

```python
# 临时换模型，地址和 key 仍读 [jev]
jev = Jev(model="jev-latest")

# 全部显式传参，根本不读配置文件
jev = Jev(
    base_url="https://api.typesafe.ai",
    api_key="apikey-xxx",
    model="jev-latest",
)
```

**接别的网关。** `base_url` 可指向任何符合 TypeSafe OpenAPI 规范的实现，因此也能用来接 OpenRouter 之类的 AI 网关，换地址即可，调用代码不变。

## 6. 小结

`pten.tools` 子包新增了一个 `Jev` 类，封装了 TypeSafe AI 的 **jev** 模型，把「让模型出结构化判断」这件事收成一行 `ask`：声明问题是 `Noul`/`Choice`/`Score`，答案类型在调用前就定死，省掉 JSON 解析和容错。它复用 pten 的配置查找链和代理体系，`[jev]` 段和其它段共处一个 `pten_keys.ini`，密钥不进代码。

- 主页：[GitHub](https://github.com/bendell02/pten) ｜ [Gitee](https://gitee.com/bendell02/pten)
- 安装：`pip install pten`（v0.4.18+）
- 可运行示例：`examples/tools/jev.py`
- 配置样例：`pten_keys_example.ini` 的 `[jev]` 段
- TypeSafe SDK 文档：https://docs.typesafe.ai/sdk/python

