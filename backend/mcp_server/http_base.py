"""MCP Server HTTP 客户端生命周期。"""

from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP

from mcp_server.server_config import MEDICAL_API_BASE


@asynccontextmanager
async def mcp_lifespan(server: FastMCP):
    """初始化 / 关闭 HTTP 客户端。"""
    http_client = httpx.AsyncClient(
        base_url=MEDICAL_API_BASE,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    )
    yield {"http_client": http_client}
    await http_client.aclose()
