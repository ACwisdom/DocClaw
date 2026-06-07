"""
MCP 工具客户端 — 连接 DocClaw MCP Server 并加载医疗工具。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.env_utils import MCP_URL

logger = logging.getLogger(__name__)

MCP_SERVER_CONFIG = {
    "docclaw-medical": {
        "url": MCP_URL,
        "transport": "streamable_http",
    },
}

# Phase 2 子 Agent 工具前缀
CLINICAL_TOOL_PREFIXES = (
    "patient_get",
    "consult_",
    "his_",
    "skill_",
)
FOLLOWUP_TOOL_PREFIXES = (
    "patient_get",
    "followup_",
    "notification_",
)


async def load_mcp_tools(
    server_config: dict | None = None,
) -> List[BaseTool]:
    """
    连接 MCP Server，加载全部医疗工具。

    Returns:
        LangChain Tool 列表（预期 18+ 个业务工具 + mcp_health）
    """
    if server_config is None:
        server_config = MCP_SERVER_CONFIG

    print(f"[MCP] 正在连接 {MCP_URL} ...")
    client = MultiServerMCPClient(server_config)
    tools = await client.get_tools(server_name="docclaw-medical")
    print(f"[MCP] 已加载 {len(tools)} 个工具: {[t.name for t in tools]}")
    return list(tools)


async def load_medical_tools_with_fallback(
    *,
    max_retries: int = 5,
    retry_delay: float = 2.0,
) -> tuple[list[BaseTool], str]:
    """
    优先加载 MCP 工具；连接失败时降级为直连 FastAPI 的本地工具。

    Returns:
        (tools, source) — source 为 "mcp" 或 "fallback"
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            tools = await load_mcp_tools()
            if tools:
                return tools, "mcp"
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "MCP 工具加载失败 (尝试 %d/%d): %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    from agent.tools.medical_api_tools import get_fallback_medical_tools

    fallback = get_fallback_medical_tools()
    logger.warning(
        "MCP 不可用，已降级为 FastAPI 直连工具 (%d 个)。最后错误: %s",
        len(fallback),
        last_exc,
    )
    print(
        f"[MCP] 降级为 FastAPI 直连工具 ({len(fallback)} 个)，"
        f"请确认 Medical API :8000 与 MCP :8001 已启动"
    )
    return fallback, "fallback"


def wait_mcp_ready(timeout: float = 120, interval: float = 2.0) -> bool:
    """阻塞等待 MCP Server 可加载工具（供 start_agent.py 使用）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            tools = asyncio.run(load_mcp_tools())
            if tools:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def filter_tools_by_prefix(tools: list, prefixes: tuple[str, ...]) -> list:
    """按工具名前缀筛选（精确名或前缀匹配）。"""
    result = []
    for tool in tools:
        name = tool.name
        if name in prefixes or any(name.startswith(p) for p in prefixes if p.endswith("_")):
            result.append(tool)
        elif any(name == p or name.startswith(p.rstrip("_") + "_") for p in prefixes):
            result.append(tool)
    return result
