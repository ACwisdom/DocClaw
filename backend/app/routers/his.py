"""HIS 门诊队列 Mock API — Agent / MCP 可调用。"""

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..services.his_queue_service import (
    get_his_queue_item,
    get_his_queue_summary,
    list_his_queue_items,
    load_his_outpatient_queue,
)

router = APIRouter(prefix="/api/his/outpatient", tags=["his"])


@router.get("/queue")
def his_outpatient_queue(
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    visit_type: Optional[str] = None,
    search: Optional[str] = None,
):
    """HIS 门诊排队列表（Mock）。"""
    return {
        "meta": load_his_outpatient_queue()["meta"],
        "items": list_his_queue_items(
            doctor_id=doctor_id,
            status=status,
            visit_type=visit_type,
            search=search,
        ),
    }


@router.get("/queue/summary")
def his_outpatient_queue_summary(doctor_id: Optional[str] = None):
    """HIS 门诊队列统计（Mock）— 待接诊 / 问诊中 / 已完成。"""
    result = get_his_queue_summary(doctor_id=doctor_id)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(404, result["error"])
    return result


@router.get("/queue/{slug}")
def his_outpatient_queue_patient(slug: str):
    """HIS 单条挂号/排队记录。"""
    item = get_his_queue_item(slug)
    if not item:
        raise HTTPException(404, "HIS 队列中未找到该患者")
    return item
