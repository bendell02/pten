
# pten : 一份配置文件支持多 LLM provider 

实际项目里常常要同时用好几家大模型：DeepSeek 做摘要、OpenAI 做翻译、本地还跑着 Ollama——只配一套反而少见。pten v0.4.6 给 `LLM` 类加了「命名 provider」机制，在一个 `pten_keys.ini` 里就能管好所有 provider，按名字切换，密钥不再散进代码。

## 1. 为什么需要多套 provider
旧的做法是把 `llm_base_url`/`llm_api_key`/`llm_model` 写在 `[notice]` 段里，但一个 `[notice]` 只能装一套配置，多用几家就捉襟见肘。
- 想同时用多家模型时，要么改配置文件再跑、要么把地址和密钥硬编码进源码，两者都别扭
- 密钥进代码有泄露风险；切模型要改源码也容易出错；多套配置并存时 `[notice]` 没地方放
- v0.4.6 引入 `[llm:<name>]` 命名段：每段一套 provider，按名字选用，密钥只留在 ini 里

## 2. 准备：版本与配置文件
动手前先确认版本到位、配置文件就位。
- 需要 pten v0.4.6 及以上；安装： `pip install pten`
- 配置文件默认是工作目录下的 `pten_keys.ini`（已被 gitignore，不进版本库），可用 `keys_filepath` 指向别的路径
- 文件是 ini 格式、UTF-8 编码；命名段固定写成 `[llm:名字]`，冒号紧贴名字，如 `[llm:openai]`
- 参考仓库里的 `pten_keys_example.ini`，里面带有 `[llm:deepseek]`/`[llm:openai]` 的注释样例，照抄改 key 即可

## 3. 基础使用：配置并按名字调用
给每个 provider 写一段 `[llm:<name>]`，再在代码里用名字取出来。
- 每段三个键：`base_url`/`api_key`/`model`，三者缺一会抛 `ValueError`

```ini
[llm:deepseek]
base_url=https://api.deepseek.com
api_key=sk-deepseek-xxxxxxxx
model=deepseek-v4-flash

[llm:openai]
base_url=https://api.openai.com/v1
api_key=sk-openai-xxxxxxxx
model=gpt-4o-mini
```

- 调用时传 `provider` 选段，参数全部从该段读取：

```python
from pten.notice import LLM

deepseek = LLM(provider="deepseek")
print(deepseek.get_completion("用一句话介绍黑洞"))

openai = LLM(provider="openai")
print(openai.get_completion("Translate 'hello' to French"))
```

- `get_completion(prompt)` 走 OpenAI 兼容的 chat completions 接口，所以任何 OpenAI 兼容服务都能配进来（DeepSeek、OpenAI、本地 Ollama/LiteLLM 等）
- 段名即 provider 名，想加一套就再写一段 `[llm:qwen]`/`[llm:local]`，互不干扰

## 4. 进阶用法：参数覆盖、默认兼容与枚举
命名段是默认来源，但不是最高优先级——显式传入的参数永远盖过配置。
- 显式参数优先于 `[llm:<name>]`，方便临时覆盖单个字段：`gpt4 = LLM(provider="openai", model="gpt-4o")` 会用配置里的 base_url/api_key，只换模型
- 不传 `provider` 时走 `[notice]` 段的 `llm_base_url`/`llm_api_key`/`llm_model` 默认配置，旧代码无需改动，完全向后兼容
- `system_prompt` 只来自构造参数（默认 `"You are a helpful assistant"`），不从配置读——角色设定走代码不走配置
- 用 `Keys.list_llm_providers()` 枚举配置文件里所有命名段，按文件中出现顺序返回：

```python
from pten.keys import Keys

keys = Keys()
print(keys.list_llm_providers())  # 例如 ['deepseek', 'openai']
```

- 老的 `Deepseek` 类已被通用 `LLM` 类取代，新代码建议直接用 `LLM`（`Deepseek` 保留仅为兼容旧代码）

## 5. 小结
一个 ini 文件、多个 `[llm:<name>]` 段、`LLM(provider=...)` 按名字切，是多 provider 场景的推荐姿势。
- 优先级链：显式参数 > `[llm:<name>]` > `[notice]` 默认，既灵活又向后兼容
- 建议：先照 `pten_keys_example.ini` 抄一段跑通 `get_completion`，再按需加 provider
