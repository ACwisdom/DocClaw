"""患者队列 MCP 工具。"""

from typing import Optional

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get, api_post

GROUP = "patient"


def register_patient_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_list")
    async def patient_list(
        status: Optional[str] = None,
        visit_type: Optional[str] = None,
        search: Optional[str] = None,
        ctx: Context = None,
    ) -> list | dict:
        """
        获取患者队列列表。

        Args:
            status: 状态筛选 waiting/consulting/completed，或 all
            visit_type: 初复诊筛选 first/followup，或 all
            search: 按姓名或主诉模糊搜索
        """
        return await api_get(
            ctx,
            "/patients",
            {"status": status, "visit_type": visit_type, "search": search},
        )

    @mcp.tool(name=f"{GROUP}_summary")
    async def patient_summary(ctx: Context = None) -> dict:
        """获取今日队列统计：待接诊、问诊中、已完成、初诊/复诊数量。"""
        result = await api_get(ctx, "/patients/summary")
        if isinstance(result, dict) and result.get("error"):
            from agent.queue_data import mock_patient_summary

            return mock_patient_summary()
        return result

    @mcp.tool(name=f"{GROUP}_get")
    async def patient_get(slug: str, ctx: Context = None) -> dict:
        """
        获取单个患者详情。

        Args:
            slug: 患者 slug，如 patient-zhang-san
        """
        return await api_get(ctx, f"/patients/{slug}")

    @mcp.tool(name=f"{GROUP}_start_consult")
    async def patient_start_consult(slug: str, ctx: Context = None) -> dict:
        """开始问诊，将患者状态从待接诊改为问诊中。"""
        return await api_post(ctx, f"/patients/{slug}/start")

    @mcp.tool(name=f"{GROUP}_complete_consult")
    async def patient_complete_consult(slug: str, ctx: Context = None) -> dict:
        """结束问诊，将患者状态改为已完成。"""
        return await api_post(ctx, f"/patients/{slug}/complete")
