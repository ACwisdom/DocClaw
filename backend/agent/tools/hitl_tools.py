"""
Human-in-the-Loop 工具集（医疗版）。

病历写入与随访计划创建须经医生确认后才会继续执行。
工具通过 langgraph.types.interrupt() 暂停执行，等待 /api/agent/resume 恢复。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def request_record_confirm(
    patient_slug: str,
    draft_content: str,
    structured_data: Optional[dict[str, Any]] = None,
) -> str:
    """请求医生确认病历草稿后再写入正式病历。

    调用此工具会暂停执行，等待医生在界面审阅并确认/拒绝/编辑草稿。

    Args:
        patient_slug: 患者 slug
        draft_content: 病历草稿正文
        structured_data: 结构化病历 JSON，可选
    """
    response = interrupt(
        {
            "type": "medical_record_confirm",
            "patient_slug": patient_slug,
            "draft_content": draft_content,
            "structured_data": structured_data or {},
        }
    )
    return json.dumps(response, ensure_ascii=False)


@tool
def request_followup_confirm(
    patient_id: str,
    title: str,
    description: str = "",
    tasks: Optional[list[dict[str, Any]]] = None,
) -> str:
    """请求医生确认随访计划后再创建。

    调用此工具会暂停执行，等待医生审阅计划内容并确认/拒绝/编辑。

    Args:
        patient_id: 患者 ID（非 slug）
        title: 随访计划标题
        description: 计划说明
        tasks: 任务列表，每项含 title、description、scheduled_at(ISO8601)
    """
    response = interrupt(
        {
            "type": "followup_plan_confirm",
            "patient_id": patient_id,
            "title": title,
            "description": description,
            "tasks": tasks or [],
        }
    )
    return json.dumps(response, ensure_ascii=False)
