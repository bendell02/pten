# 用pten做LLM的url、api_key和model_name的分发网关

pten v0.4.19 给 `tools` 子包新增了 `ai_gateway`——一个 LLM 凭证分发网关。它把 agent 应用里会变的 `api_key`、`url`、`model_name` 从代码里抽出来，集中在服务端保管，agent 启动时来取、拿到后**直连 LLM provider**，网关只发证、不代理流量。传输复用 pten 自带的 `wwcrypt`（`WXBizMsgCrypt`）做 签名和加解密，请求和响应都是自包含的加密 XML 信封。

## 1. 问题：api_key 分发与 model name 过期

做 agent 应用时，LLM 凭证管理有两个反复出现的痛点，它们本质上是同一类问题——**会变的凭证被固化进了 agent 的代码或配置**。

- **api_key 分发难**：每个 agent 都得持有 LLM 的 `api_key` 才能跑；api_key 散落在多台机器、多个仓库、多份配置里。一旦泄露或需要轮换，得逐个 agent 改一遍，还难以确认是否清理干净——api_key 落在哪台机器上，吊销时就得多怀疑一台。
- **model name 过期**：厂商会下线或改名旧 model（例如某版本 flash 改名），agent 代码里硬编码的 `model_name` 一夜之间集体报 `model not found`，又得逐个改代码重新部署。
- 如果自己做统一官网，所有流量都走网关，网关就很重，无法自己做负载均衡时，容易成为瓶颈或单点故障。

`api_key`、`url`、`model_name` 这三元组是"会变"的运营态，却被当成了"不变"的代码常量——这就是两个痛点的共同根源。把它们从 agent 代码里挪出去、交给一个集中发证的服务，是解决方向。

## 2. 思路：纯发证，不代理流量

`ai_gateway` 按这个方向设计，几个关键取舍：

- **集中保管**：真实 LLM 的 `api_key`/`url`/`model` 只写在服务端一份配置（`ai_gateway_server.ini`）里，agent 侧不持有任何明文凭证。
- **按 client_id 发证**：服务端为每个 agent 配一段 `[client:<id>]`，取凭证时带上 `client_id` 就拿到属于它的那组；缺省可回落 `[client:default]`，让所有 agent 共用一组。
- **纯发证、不代理流量**：网关只下发三元组，agent 拿到后用自己的 OpenAI client 直连 provider——网关不经过任何 LLM 请求，因此不会成为延迟瓶颈或单点故障。这和"把 LLM 请求都路由过网关"的代理方案是两条路。
- **带有效期**：网关给每张凭证签发 `expire_at`（`now + ttl_days`，默认 90 天）。model 改名只需在服务端改一行，凭证过期后 agent 自动取到新值，不用动 agent 代码。
- **传输加密**：取凭证的请求和响应都用 `wwcrypt` 的 SHA1 签名 + AES-CBC 加密成 XML 信封自包含传输，共享密钥（`token`/`aes_key`/`receive_id`）服务端与客户端各配一份、一致即可。
- **容灾**：客户端内存 + 磁盘双缓存（缓存键 `sha1(client_id)`，不明文落盘），网关不可达时降级到未过期缓存继续跑；服务端配置按 ini 的 mtime 热重载，改配置不用重启。

## 3. 安装

`ai_gateway` 分客户端和服务端两套依赖——agent 侧只要装 pten 本身，服务端多装一个 fastapi/uvicorn extras。

- agent 侧（客户端）：`pip install pten`。客户端只依赖 `requests` 和 pten 自带的 `wwcrypt`，都在主依赖里。
- 服务端：`pip install pten[ai_gateway]`，extras 带 `fastapi`、`uvicorn`。
- 需要 Python ≥ 3.10；也可源码安装：克隆仓库后 `pip install -e .`。
- 验证客户端就绪：

```bash
python -c "from pten.tools.ai_gateway import AIGatewayClient, AIGatewayLLM"
```

- pten 主页：[GitHub](https://github.com/bendell02/pten) ｜ [Gitee](https://gitee.com/bendell02/pten) ｜ [PyPI](https://pypi.org/project/pten/)

## 4. 起服务端

服务端是一个 FastAPI 应用，配置写在 `ai_gateway_server.ini` 里（真实 api_key，已 gitignore），仓库里的 `ai_gateway_server_example.ini` 是假凭证样板：

```ini
[gateway]
;全网关共享的签名 token、AES 密钥与 receive_id，客户端 [ai_gateway] 段须与此一致
token=shared_msg_token
aes_key=9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO
receive_id=shared_receive_id
;下发的 expire_at 有效期天数（api_key/url/model 共享）
ttl_days=90

[client:default]
;该 agent 取到的 LLM 凭证（假凭证，仅供测试/示例）
api_key=sk-real-xxxxxxxxxxxxwxyz
url=https://api.deepseek.com
model=deepseek-v4-flash

[client:agent-x]
;该 agent 取到的 LLM 凭证（假凭证，仅供测试/示例）
api_key=sk-real-xxxxxxxxxxxxwxyz
url=https://api.deepseek.com
model=deepseek-v4-flash
```

一个 `[gateway]` 段配全网关共享的密钥材料与 `ttl_days`；每个 agent 一个 `[client:<client_id>]` 段配它的 `api_key`/`url`/`model`。想加一套就再写一段 `[client:agent-y]`，互不干扰。

启动用 uvicorn factory 模式（避免 import 时读配置）：

```bash
uvicorn pten.tools.ai_gateway.server:create_app --factory --reload
```

配置文件路径默认取 `./ai_gateway_server.ini`；想指到别处，设环境变量 `AI_GATEWAY_CONFIG=/path/to/ai_gateway_server.ini` 再启动。也可直接跑示例脚本 `python examples/ai_gateway/run_server.py`，缺配置时它会自动回落到 example ini 并提示。

服务起来后只有一个端点 `POST /credentials`：请求体是加密 XML 信封，响应也是加密信封，里面是 `client_id`/`api_key`/`url`/`model`/`expire_at` 五个字段。改配置不用重启——服务端按 ini 的 mtime 懒重载，文件变了才重读，没变零开销；改坏了保留旧配置继续服务并打 error 日志，不影响在跑的请求。

## 5. agent 端取凭证与对话

agent 侧在 `pten_keys.ini` 配一段 `[ai_gateway]` 指向服务端，`token`/`aes_key`/`receive_id` 须与服务端 `[gateway]` 段一致：

```ini
[ai_gateway]
;LLM 凭证网关客户端：gateway_url 指向自建的 ai_gateway 服务端
;token/aes_key/receive_id 须与服务端 [gateway] 段一致
gateway_url=http://localhost:8000/credentials
;client_id 可选：缺省时网关回落服务端的 [client:default] 段（所有 agent 共用一组凭证）
client_id=agent-x
token=shared_msg_token
aes_key=9z1Cj9cSd7WtEV3hOWo5iMQlFkSP9Td1ejzsV9WhCmO
receive_id=shared_receive_id
```

`client_id` 可省：省略时请求不带 `client_id`，网关回落服务端的 `[client:default]` 段，所有 agent 共用一组凭证。配置文件还是走 pten 一贯的查找链：`keys_filepath` 参数显式指定 → `PTEN_KEYS_FILE` 环境变量 → 当前目录的 `pten_keys.ini` → 用户主目录 `~/.pten/pten_keys.ini`（前两级严格、后两级探测）。`[ai_gateway]` 段可以和 `[ww]`/`[fs]`/`[notice]` 等段并存于同一个 `pten_keys.ini`，密钥不进代码、不进版本库（`pten_keys.ini` 已 gitignore）。

**取凭证三元组。** `AIGatewayClient().get_credentials()` 返回一个 dict：

```python
from pten.tools.ai_gateway import AIGatewayClient

client = AIGatewayClient()          # 读 [ai_gateway] 段；也可直接传参
bundle = client.get_credentials()
# bundle = {"client_id":..., "api_key":..., "url":..., "model":..., "expire_at":...}
# 拿到后用 bundle["api_key"]/["url"] 自行构造 OpenAI client 直连 provider
```

**一行对话。** 不想自己拼 OpenAI client，用 `AIGatewayLLM`——构造时自动向网关取 `api_key`/`url`/`model`，之后直接问：

```python
from pten.tools.ai_gateway import AIGatewayLLM

llm = AIGatewayLLM()                # 构造时自动取凭证
print(llm.get_completion("简略介绍一下牛顿"))
```

几个要点：

- `AIGatewayLLM` 不继承 `notice.LLM`，只复刻 `get_completion` 接口，用法与 `notice.LLM` 一致；`system_prompt` 可选，默认 `"You are a helpful assistant"`。
- 不想读配置文件也可全用显式参数：`AIGatewayClient(gateway_url=..., client_id=..., token=..., aes_key=..., receive_id=...)`，或传共享的 `keys=Keys(...)` 实例。
- 取到的凭证内存 + 磁盘双缓存，缓存文件 `ai_gateway_cache.json` 落在 keys 文件同目录（不会散到 CWD）；网关不可达时自动降级到未过期缓存，`get_credentials(force_refresh=True)` 可强制刷新。
- 仓库里 `examples/ai_gateway/` 有三个可跑示例：`run_server.py`（起服务端）→ `get_credentials.py`（取凭证）→ `llm_chat.py`（一行对话），按这个顺序跑通本地链路最顺。

## 6. 小结

`ai_gateway` 用一个"纯发证"的轻量服务，把 agent 应用里会变的 LLM 凭证（`api_key`/`url`/`model_name`）从代码里抽出来集中管——api_key 轮换改服务端一行、model 改名改服务端一行，agent 凭证过期后自动取到新值，既解决 api_key 分发也解决 model 过期。

- 适合场景：多个 agent 共用同一批 LLM、需要集中轮换 api_key 或 model、不想把明文凭证散落到各 agent 机器。
- 安全根是共享的 `token`/`aes_key`/`receive_id`，服务端与所有客户端各配一份且必须一致；真实 `ai_gateway_server.ini` 与 `ai_gateway_cache.json` 都已 gitignore，别提交。
- 主页：[GitHub](https://github.com/bendell02/pten) ｜ [Gitee](https://gitee.com/bendell02/pten) ｜ [PyPI](https://pypi.org/project/pten/)
- 安装：`pip install pten`（客户端）／ `pip install pten[ai_gateway]`（服务端），v0.4.19+
- 可运行示例：`examples/ai_gateway/`；配置样例：`ai_gateway_server_example.ini` 与 `pten_keys_example.ini` 的 `[ai_gateway]` 段
