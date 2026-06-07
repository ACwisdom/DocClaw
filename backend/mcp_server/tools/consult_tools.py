"""问诊对话 MCP 工具。"""

from typing import Optional

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get, api_post

GROUP = "consult"


def register_consult_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_get_messages")
    async def consult_get_messages(slug: str, ctx: Context = None) -> list | dict:
        """
        获取问诊对话历史。

        Args:
            slug: 患者 slug
        """
        return await api_get(ctx, f"/consult/{slug}/messages")

    @mcp.tool(name=f"{GROUP}_send_message")
    async def consult_send_message(
        slug: str,
        content: str,
        role: str = "assistant",
        ctx: Context = None,
    ) -> dict:
        """
        Agent 内部写回问诊消息（不触发 Skill Runtime）。

        Args:
            slug: 患者 slug
            content: 消息正文
            role: 角色 assistant/system，默认 assistant
        """
        return await api_post(
            ctx,
            f"/consult/{slug}/messages/agent",
            {"content": content, "role": role},
        )
