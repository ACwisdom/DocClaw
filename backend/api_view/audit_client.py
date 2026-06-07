"""Agent API → 医疗业务 API 审计上报客户端。"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from agent.env_utils import MEDICAL_API_BASE_URL

logger = logging.getLogger(__name__)


async def report_tool_call_start(
    *,
    doctor_id: str,
    thread_id: str,
    tool_name: str,
    tool_call_id: str,
    source: str = "main",
    args_snapshot: str = "",
    patient_slug: Optional[str] = None,
) -> None:
    payload = {
        "doctor_id": doctor_id,
        "thread_id": thread_id,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "source": source,
        "args_snapshot": args_snapshot[:4000],
        "patient_slug": patient_slug,
    }
    await _post("/audit/agent-tools/start", payload)


async def report_tool_call_finish(
    *,
    doctor_id: str,
    thread_id: str,
    tool_name: str,
    tool_call_id: str,
    result_text: str = "",
    source: str = "main",
    status: str = "success",
    patient_slug: Optional[str] = None,
) -> None:
    payload = {
        "doctor_id": doctor_id,
        "thread_id": thread_id,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "result_text": result_text[:8000],
        "source": source,
        "status": status,
        "patient_slug": patient_slug,
    }
    await _post("/audit/agent-tools/finish", payload)


async def _post(path: str, payload: dict) -> None:
    url = f"{MEDICAL_API_BASE_URL.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                logger.warning("审计上报失败 %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("审计上报异常: %s", exc)
