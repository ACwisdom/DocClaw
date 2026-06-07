"""Direct FastAPI fallback tools — MCP 不可用时 Agent 仍可查询业务数据。"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from langchain_core.tools import BaseTool, tool

from agent.env_utils import MEDICAL_API_BASE_URL
from agent.queue_data import fetch_patient_summary

_BASE = MEDICAL_API_BASE_URL.rstrip("/")


async def _api_get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(base_url=_BASE, timeout=30.0) as client:
        try:
            resp = await client.get(path, params=_clean_params(params))
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return {"error": str(exc)}


async def _api_post(path: str, json_body: dict | None = None) -> Any:
    async with httpx.AsyncClient(base_url=_BASE, timeout=30.0) as client:
        try:
            resp = await client.post(path, json=json_body or {})
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return {"error": str(exc)}


def _clean_params(params: dict | None) -> dict | None:
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None}


@tool("patient_summary")
async def patient_summary() -> dict:
    """获取今日队列统计：待接诊、问诊中、已完成、初诊/复诊数量。"""
    return await fetch_patient_summary()


@tool("patient_list")
async def patient_list(
    status: Optional[str] = None,
    visit_type: Optional[str] = None,
    search: Optional[str] = None,
) -> list | dict:
    """
    获取患者队列列表。

    Args:
        status: 状态筛选 waiting/consulting/completed，或 all
        visit_type: 初复诊筛选 first/followup，或 all
        search: 按姓名或主诉模糊搜索
    """
    return await _api_get(
        "/patients",
        {"status": status, "visit_type": visit_type, "search": search},
    )


@tool("patient_get")
async def patient_get(slug: str) -> dict:
    """
    获取单个患者详情。

    Args:
        slug: 患者 slug，如 patient-zhang-san
    """
    return await _api_get(f"/patients/{slug}")


@tool("patient_start_consult")
async def patient_start_consult(slug: str) -> dict:
    """开始问诊，将患者状态从待接诊改为问诊中。"""
    return await _api_post(f"/patients/{slug}/start")


@tool("patient_complete_consult")
async def patient_complete_consult(slug: str) -> dict:
    """结束问诊，将患者状态改为已完成。"""
    return await _api_post(f"/patients/{slug}/complete")


@tool("consult_get_messages")
async def consult_get_messages(slug: str) -> list | dict:
    """
    获取问诊对话历史。

    Args:
        slug: 患者 slug
    """
    return await _api_get(f"/consult/{slug}/messages")


@tool("consult_send_message")
async def consult_send_message(
    slug: str,
    content: str,
    role: str = "assistant",
) -> dict:
    """
    Agent 内部写回问诊消息。

    Args:
        slug: 患者 slug
        content: 消息正文
        role: 角色 assistant/system，默认 assistant
    """
    return await _api_post(
        f"/consult/{slug}/messages/agent",
        {"content": content, "role": role},
    )


@tool("his_queue_summary")
async def his_queue_summary(doctor_id: Optional[str] = None) -> dict:
    """
    获取 HIS 门诊队列统计：待接诊、问诊中、已完成（Mock 数据源）。

    Args:
        doctor_id: 可选，医生 ID，如 doctor-li
    """
    result = await _api_get(
        "/his/outpatient/queue/summary",
        {"doctor_id": doctor_id},
    )
    if isinstance(result, dict) and result.get("error"):
        from agent.queue_data import mock_patient_summary

        return {**mock_patient_summary(), "source": "his-mock"}
    return result


@tool("his_get_outpatient_queue")
async def his_get_outpatient_queue(
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    visit_type: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """
    获取 HIS 门诊排队列表（Mock）。

    Args:
        doctor_id: 医生 ID
        status: waiting/consulting/completed 或 all
        visit_type: first/followup 或 all
        search: 姓名或主诉关键词
    """
    return await _api_get(
        "/his/outpatient/queue",
        {
            "doctor_id": doctor_id,
            "status": status,
            "visit_type": visit_type,
            "search": search,
        },
    )


@tool("his_get_labs")
async def his_get_labs(slug: str) -> dict:
    """
    获取患者已完成检查结果。

    Args:
        slug: 患者 slug
    """
    patient = await _api_get(f"/patients/{slug}")
    if isinstance(patient, dict) and patient.get("error"):
        return patient
    return {
        "patient_slug": slug,
        "patient_name": patient.get("name"),
        "completed_exams": patient.get("completed_exams", ""),
    }


@tool("his_get_history")
async def his_get_history(slug: str) -> dict:
    """
    获取患者既往史/重点提示。

    Args:
        slug: 患者 slug
    """
    patient = await _api_get(f"/patients/{slug}")
    if isinstance(patient, dict) and patient.get("error"):
        return patient
    return {
        "patient_slug": slug,
        "patient_name": patient.get("name"),
        "key_notes": patient.get("key_notes", ""),
        "first_visit_note": patient.get("first_visit_note", ""),
    }


@tool("his_write_record")
async def his_write_record(
    slug: str,
    content: str,
    structured_data: Optional[dict[str, Any]] = None,
) -> dict:
    """
    HITL 确认后写入正式病历。

    Args:
        slug: 患者 slug
        content: 病历正文
        structured_data: 结构化病历 JSON，可选
    """
    body: dict[str, Any] = {"content": content}
    if structured_data is not None:
        body["structured_data"] = structured_data
    return await _api_post(f"/medical-records/{slug}/confirm", body)


@tool("skill_list")
async def skill_list() -> list | dict:
    """获取医生已启用的技能列表。"""
    data = await _api_get("/skills")
    if isinstance(data, list):
        return [s for s in data if s.get("enabled")]
    return data


@tool("skill_get")
async def skill_get(skill_id: str) -> dict:
    """
    获取技能详情。

    Args:
        skill_id: 技能 ID
    """
    return await _api_get(f"/skills/{skill_id}")


@tool("followup_list_plans")
async def followup_list_plans(patient_id: Optional[str] = None) -> list | dict:
    """
    获取随访计划列表。

    Args:
        patient_id: 可选，按患者 ID 筛选
    """
    return await _api_get("/followup", {"patient_id": patient_id})


@tool("followup_create_plan")
async def followup_create_plan(
    patient_id: str,
    title: str,
    description: str = "",
    skill_id: Optional[str] = None,
    tasks: Optional[list[dict[str, Any]]] = None,
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
    return await _api_post("/followup", body)


@tool("followup_pending_tasks")
async def followup_pending_tasks() -> list | dict:
    """获取所有待执行的随访任务。"""
    return await _api_get("/followup/tasks/pending")


@tool("followup_execute_task")
async def followup_execute_task(task_id: str, note: str = "") -> dict:
    """
    执行随访任务。

    Args:
        task_id: 任务 ID
        note: 医生执行备注
    """
    return await _api_post(f"/followup/tasks/{task_id}/execute", {"note": note})


@tool("notification_list")
async def notification_list() -> list | dict:
    """获取通知列表。"""
    return await _api_get("/notifications")


@tool("notification_create")
async def notification_create(title: str, content: str) -> dict:
    """
    创建患者触达/提醒通知。

    Args:
        title: 通知标题
        content: 通知内容
    """
    return await _api_post("/notifications", {"title": title, "content": content})


FALLBACK_MEDICAL_TOOLS: list[BaseTool] = [
    patient_summary,
    patient_list,
    patient_get,
    patient_start_consult,
    patient_complete_consult,
    consult_get_messages,
    consult_send_message,
    his_queue_summary,
    his_get_outpatient_queue,
    his_get_labs,
    his_get_history,
    his_write_record,
    skill_list,
    skill_get,
    followup_list_plans,
    followup_create_plan,
    followup_pending_tasks,
    followup_execute_task,
    notification_list,
    notification_create,
]

MAIN_PATIENT_TOOL_NAMES = (
    "patient_summary",
    "patient_list",
    "patient_get",
    "his_queue_summary",
    "his_get_outpatient_queue",
)


def get_fallback_medical_tools() -> list[BaseTool]:
    """返回与 MCP 同名、直连 FastAPI 的降级工具集。"""
    return list(FALLBACK_MEDICAL_TOOLS)


def pick_tools_by_name(tools: list, names: tuple[str, ...]) -> list:
    """按工具名选取子集（保持 names 顺序）。"""
    index = {getattr(t, "name", None): t for t in tools}
    return [index[n] for n in names if n in index]
