"""通知 MCP 工具。"""

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get, api_post

GROUP = "notification"


def register_notification_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_list")
    async def notification_list(ctx: Context = None) -> list | dict:
        """获取通知列表。"""
        return await api_get(ctx, "/notifications")

    @mcp.tool(name=f"{GROUP}_create")
    async def notification_create(
        title: str,
        content: str,
        ctx: Context = None,
    ) -> dict:
        """
        创建患者触达/提醒通知。

        Args:
            title: 通知标题
            content: 通知内容
        """
        return await api_post(ctx, "/notifications", {"title": title, "content": content})
