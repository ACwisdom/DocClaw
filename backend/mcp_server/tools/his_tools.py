"""HIS 对接 MCP 工具（MVP Mock，基于患者数据）。"""

from typing import Any, Optional

from fastmcp import Context, FastMCP

from mcp_server.tools._helpers import api_get, api_post

GROUP = "his"


def register_his_tools(mcp: FastMCP) -> None:
    @mcp.tool(name=f"{GROUP}_queue_summary")
    async def his_queue_summary(
        doctor_id: Optional[str] = None,
        ctx: Context = None,
    ) -> dict:
        """
        获取 HIS 门诊队列统计：待接诊、问诊中、已完成等（Mock 数据源）。

        Args:
            doctor_id: 可选，按医生 ID 筛选，如 doctor-li
        """
        result = await api_get(
            ctx,
            "/his/outpatient/queue/summary",
            {"doctor_id": doctor_id},
        )
        if isinstance(result, dict) and result.get("error"):
            from agent.queue_data import mock_patient_summary

            summary = mock_patient_summary()
            return {**summary, "source": "his-mock"}
        return result

    @mcp.tool(name=f"{GROUP}_get_outpatient_queue")
    async def his_get_outpatient_queue(
        doctor_id: Optional[str] = None,
        status: Optional[str] = None,
        visit_type: Optional[str] = None,
        search: Optional[str] = None,
        ctx: Context = None,
    ) -> dict:
        """
        获取 HIS 门诊排队列表（Mock）。

        Args:
            doctor_id: 医生 ID，如 doctor-li
            status: waiting/consulting/completed 或 all
            visit_type: first/followup 或 all
            search: 按姓名或主诉搜索
        """
        return await api_get(
            ctx,
            "/his/outpatient/queue",
            {
                "doctor_id": doctor_id,
                "status": status,
                "visit_type": visit_type,
                "search": search,
            },
        )

    @mcp.tool(name=f"{GROUP}_get_labs")
    async def his_get_labs(slug: str, ctx: Context = None) -> dict:
        """
        获取患者已完成检查结果（MVP：来自 patient.completed_exams）。

        Args:
            slug: 患者 slug
        """
        patient = await api_get(ctx, f"/patients/{slug}")
        if isinstance(patient, dict) and patient.get("error"):
            return patient
        return {
            "patient_slug": slug,
            "patient_name": patient.get("name"),
            "completed_exams": patient.get("completed_exams", ""),
        }

    @mcp.tool(name=f"{GROUP}_get_history")
    async def his_get_history(slug: str, ctx: Context = None) -> dict:
        """
        获取患者既往史/重点提示（MVP：来自 patient.key_notes）。

        Args:
            slug: 患者 slug
        """
        patient = await api_get(ctx, f"/patients/{slug}")
        if isinstance(patient, dict) and patient.get("error"):
            return patient
        return {
            "patient_slug": slug,
            "patient_name": patient.get("name"),
            "key_notes": patient.get("key_notes", ""),
            "first_visit_note": patient.get("first_visit_note", ""),
        }

    @mcp.tool(name=f"{GROUP}_write_record")
    async def his_write_record(
        slug: str,
        content: str,
        structured_data: Optional[dict[str, Any]] = None,
        ctx: Context = None,
    ) -> dict:
        """
        HITL 确认后写入正式病历到问诊记录。

        Args:
            slug: 患者 slug
            content: 病历正文
            structured_data: 结构化病历 JSON，可选
        """
        body: dict[str, Any] = {"content": content}
        if structured_data is not None:
            body["structured_data"] = structured_data
        return await api_post(ctx, f"/medical-records/{slug}/confirm", body)
