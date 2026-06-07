"""技能 MCP 工具。"""

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get

GROUP = "skill"


def register_skill_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_list")
    async def skill_list(ctx: Context = None) -> list | dict:
        """获取医生已启用的技能列表。"""
        data = await api_get(ctx, "/skills")
        if isinstance(data, list):
            return [s for s in data if s.get("enabled")]
        return data

    @mcp.tool(name=f"{GROUP}_get")
    async def skill_get(skill_id: str, ctx: Context = None) -> dict:
        """
        获取技能详情。

        Args:
            skill_id: 技能 ID
        """
        return await api_get(ctx, f"/skills/{skill_id}")
