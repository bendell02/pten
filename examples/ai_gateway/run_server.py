"""启动 ai_gateway 凭证网关服务端示例。

推荐用 uvicorn factory 模式启动（配置文件经 AI_GATEWAY_CONFIG 环境变量
或默认 ./ai_gateway_server.ini 解析）::

    uvicorn pten.tools.ai_gateway.server:create_app --factory --reload

也可直接运行本脚本（需安装 ai_gateway extras：pip install pten[ai_gateway]）::

    python examples/ai_gateway/run_server.py

服务端配置见 ai_gateway_server_example.ini；真实部署用 ai_gateway_server.ini
（已 gitignore，含真实 LLM key）。
"""

# 起服务端前先准备配置文件；此处仅作可运行示例
import os

from pten.tools.ai_gateway.server import create_app

if __name__ == "__main__":
    import uvicorn

    # 可显式指定配置；否则取 AI_GATEWAY_CONFIG 环境变量或 ./ai_gateway_server.ini
    if not os.environ.get("AI_GATEWAY_CONFIG") and not os.path.isfile(
        "ai_gateway_server.ini"
    ):
        print("未找到 ai_gateway_server.ini，将使用 ai_gateway_server_example.ini")
        os.environ["AI_GATEWAY_CONFIG"] = "ai_gateway_server_example.ini"

    uvicorn.run(create_app, factory=True, host="0.0.0.0", port=8000)
