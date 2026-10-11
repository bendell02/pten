"""向 ai_gateway 服务端取 LLM 凭证三元组示例。

运行前提：
  - 配置 pten_keys.ini 的 [ai_gateway] 段（gateway_url/client_id/token/aes_key/receive_id）
  - 起好服务端：uvicorn pten.tools.ai_gateway.server:create_app --factory
    （服务端配置 ai_gateway_server.ini 里 [client:<client_id>] 段含真实 LLM key）
运行方式：python examples/ai_gateway/get_credentials.py
"""

from pten.tools.ai_gateway import AIGatewayClient
from pten.tools.ai_gateway.protocol import mask_api_key

if __name__ == "__main__":
    # 读 [ai_gateway] 段；也可直接传参 AIGatewayClient(gateway_url=..., client_id=..., ...)
    client = AIGatewayClient()
    bundle = client.get_credentials()

    info = f"取到凭证：\n  client_id : {bundle['client_id']}\n  api_key   : {mask_api_key(bundle['api_key'])}\n  url       : {bundle['url']}\n  model     : {bundle['model']}\n  expire_at : {bundle['expire_at']}"
    print(info)
