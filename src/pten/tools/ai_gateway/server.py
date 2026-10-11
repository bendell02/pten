"""pten.tools.ai_gateway.server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

凭证网关 FastAPI HTTP 层：单端点 ``POST /credentials``，纯发证、不代理 LLM 流量。

运行方式（factory 模式，避免 import 时读配置）::

    uvicorn pten.tools.ai_gateway.server:create_app --factory

或指定配置文件 ::

    AI_GATEWAY_CONFIG=/path/to/ai_gateway_server.ini \
        uvicorn pten.tools.ai_gateway.server:create_app --factory
"""

import os

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse

from ... import logger
from .issuer import CredentialIssuer, GatewayError, load_config

__all__ = ["create_app"]

# 服务端配置文件路径的环境变量名
_CONFIG_ENV_VAR = "AI_GATEWAY_CONFIG"
# 默认配置文件名（相对 CWD）
_DEFAULT_CONFIG_FILE = "ai_gateway_server.ini"


def create_app(ini_path=None) -> FastAPI:
    """构造 FastAPI 应用并装载 CredentialIssuer。

    :param ini_path: 服务端配置文件路径；为 None 时取
        ``AI_GATEWAY_CONFIG`` 环境变量，再回落 ``./ai_gateway_server.ini``
    :return: 装配好 issuer 的 :class:`FastAPI`

    启动时加载一次配置；运行时每个请求按 ini 文件 mtime 懒重载——
    文件变了才重读，没变零开销。重载失败（ini 改坏）时保留旧 issuer
    继续服务并打 error 日志，不影响在跑的请求。
    """
    if ini_path is None:
        ini_path = os.environ.get(_CONFIG_ENV_VAR) or _DEFAULT_CONFIG_FILE

    issuer = load_config(ini_path)
    app = FastAPI(title="pten ai_gateway")
    app.state.issuer = issuer
    app.state.ini_path = ini_path
    app.state.ini_mtime = _mtime(ini_path)

    @app.post("/credentials")
    async def credentials(request: Request):
        issuer = _ensure_fresh_issuer(request.app)
        try:
            body = (await request.body()).decode("utf-8")
            # 丢进线程池执行避免阻塞事件循环
            resp_xml = await run_in_threadpool(issuer.issue, body)
        except GatewayError as e:
            return JSONResponse({"code": e.code, "msg": e.msg}, status_code=e.status)
        except UnicodeDecodeError as e:
            err = f"请求体非 UTF-8: {e}"
            return JSONResponse({"code": "BAD_ENCODING", "msg": err}, status_code=400)
        return PlainTextResponse(resp_xml, media_type="application/xml")

    return app


def _mtime(ini_path):
    """取 ini 文件 mtime；文件不存在返回 None。"""
    try:
        return os.stat(ini_path).st_mtime
    except OSError:
        return None


def _ensure_fresh_issuer(app) -> CredentialIssuer:
    """按 ini mtime 懒重载：变了才重读，没变用缓存的 issuer。

    重载失败（ini 改坏、文件被删）时保留旧 issuer 继续服务，打 error 日志。
    """
    last = getattr(app.state, "ini_mtime", None)
    cur = _mtime(app.state.ini_path)
    if cur is not None and cur != last:
        try:
            new_issuer = load_config(app.state.ini_path)
            app.state.issuer = new_issuer
            app.state.ini_mtime = cur
            logger.info(f"ai_gateway 配置已热重载: {app.state.ini_path}")
            return new_issuer
        except Exception as e:
            # 保留旧 issuer 继续服务；记录当前 mtime 避免每次请求都重试重载
            app.state.ini_mtime = cur
            err = f"ai_gateway 配置热重载失败，保留旧配置继续服务: {e}"
            logger.error(err)
    return app.state.issuer
