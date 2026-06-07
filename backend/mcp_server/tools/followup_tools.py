"""随访计划 MCP 工具。"""

from typing import Any, Optional

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get, api_post

GROUP = "followup"


def register_followup_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_list_plans")
    async def followup_list_plans(
        patient_id: Optional[str] = None,
        ctx: Context = None,
    ) -> list | dict:
        """
        获取随访计划列表。

        Args:
            patient_id: 可选，按患者 ID 筛选
        """
        return await api_get(ctx, "/followup", {"patient_id": patient_id})

    @mcp.tool(name=f"{GROUP}_create_plan")
    async def followup_create_plan(
        patient_id: str,
        title: str,
        description: str = "",
        skill_id: Optional[str] = None,
        tasks: Optional[list[dict[str, Any]]] = None,
        ctx: Context = None,
    ) -> dict:
        """
        创建随访计划（须在 HITL 确认后调用）。

        Args:
            patient_id: 患者 ID（非 slug）
            title: 计划标题
            description: 计划说明
            skill_id: 关联技能 ID，可选
            tasks: 任务列表，每项含 title、description、scheduled_at(ISO8601)
        """
        body: dict[str, Any] = {
            "patient_id": patient_id,
            "title": title,
            "description": description,
            "tasks": tasks or [],
        }
        if skill_id:
            body["skill_id"] = skill_id
        return await api_post(ctx, "/followup", body)

    @mcp.tool(name=f"{GROUP}_pending_tasks")
    async def followup_pending_tasks(ctx: Context = None) -> list | dict:
        """获取所有待执行的随访任务。"""
        return await api_get(ctx, "/followup/tasks/pending")

    @mcp.tool(name=f"{GROUP}_execute_task")
    async def followup_execute_task(
        task_id: str,
        note: str = "",
        ctx: Context = None,
    ) -> dict:
        """
        执行随访任务。

        Args:
            task_id: 任务 ID
            note: 医生执行备注
        """
        return await api_post(ctx, f"/followup/tasks/{task_id}/execute", {"note": note})
