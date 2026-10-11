"""ai_gateway 打包、导出与配置接入测试。"""

import sys


def test_tools_exports_ai_gateway():
    """pten.tools 导出 AIGatewayClient / AIGatewayLLM。"""
    from pten.tools import AIGatewayClient, AIGatewayLLM

    assert AIGatewayClient is not None
    assert AIGatewayLLM is not None


def test_tools_import_does_not_load_server():
    """import pten.tools 不得触发 server / fastapi 加载（客户端保持轻量）。"""
    sys.modules.pop("pten.tools.ai_gateway.server", None)
    import importlib

    importlib.import_module("pten.tools")
    assert "pten.tools.ai_gateway.server" not in sys.modules


def test_client_keys_example_section():
    """pten_keys_example.ini 含 [ai_gateway] 段且字段齐全。"""
    from pten.keys import Keys

    keys = Keys("pten_keys_example.ini")
    assert keys.get_key("ai_gateway", "gateway_url").startswith("http://")
    assert keys.get_key("ai_gateway", "client_id") == "agent-x"
