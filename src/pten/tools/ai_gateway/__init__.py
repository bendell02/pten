"""pten.tools.ai_gateway —— LLM 凭证网关（server + client）。

客户端类从此处导出；server 模块仅在显式 import 时加载 fastapi。
"""

from .client import AIGatewayClient, AIGatewayLLM

__all__ = ["AIGatewayClient", "AIGatewayLLM"]
