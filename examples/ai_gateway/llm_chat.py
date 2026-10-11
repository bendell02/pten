"""通过 ai_gateway 取凭证后做一次 LLM 对话示例（OpenAI 兼容）。

AIGatewayLLM 构造时自动向网关取 api_key/url/model，agent 无需持有任何凭证。
system_prompt 可选，默认 "You are a helpful assistant"。

运行前提：
  - 配置 pten_keys.ini 的 [ai_gateway] 段
  - 起好服务端（见 get_credentials.py）
运行方式：python examples/ai_gateway/llm_chat.py
"""

from pten.tools.ai_gateway import AIGatewayLLM

if __name__ == "__main__":
    llm = AIGatewayLLM()
    print(llm.get_completion("简略介绍一下牛顿"))
