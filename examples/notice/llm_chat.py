"""LLM（OpenAI 兼容大模型）对话示例。

运行前提（三选一）：
  - 修改下方常量，直接传参（任何 OpenAI 兼容服务均可）
  - 配置 [llm:<name>] provider 段，用 LLM(provider="<name>")
  - 配置 [notice] 段的 llm_base_url / llm_api_key / llm_model，用 LLM()
运行方式：python examples/notice/llm_chat.py
"""

from pten.notice import LLM

# 换成你的模型服务参数
BASE_URL = "https://api.deepseek.com"
API_KEY = "sk-xxxxxxxxxxxxxxxx"
MODEL = "deepseek-v4-flash"

if __name__ == "__main__":
    # 方式一：直接传参；system_prompt 可选，默认 "You are a helpful assistant"
    llm = LLM(base_url=BASE_URL, api_key=API_KEY, model=MODEL)
    print(llm.get_completion("简略介绍一下牛顿"))

    # 方式二：按名字读 [llm:<name>] provider 段，直接传参仍可覆盖单个字段；
    # 可用 Keys.list_llm_providers() 枚举配置文件里有哪些 provider
    # from pten.keys import Keys
    # print(Keys().list_llm_providers())  # 例如 ['deepseek', 'openai']
    # llm = LLM(provider="deepseek")
    # print(llm.get_completion("用一句话介绍黑洞"))

    # 方式三：读 [notice] 段的 llm_* 默认配置
    # llm = LLM()
    # print(llm.get_completion("Translate 'hello' to French"))
