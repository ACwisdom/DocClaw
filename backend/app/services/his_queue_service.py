"""HIS 门诊队列 Mock 服务 — 读取 his_outpatient_queue.json，供 API / Agent 调用。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

MOCK_DIR = Path(__file__).resolve().parent.parent.parent / "mock"
HIS_QUEUE_FILE = MOCK_DIR / "his_outpatient_queue.json"

STATUS_TO_LOCAL = {
    "WAITING": "waiting",
    "IN_CONSULT": "consulting",
    "COMPLETED": "completed",
}


def _ensure_his_queue_file() -> Path:
    if not HIS_QUEUE_FILE.exists():
        from mock.his_queue_builder import write_his_outpatient_queue_json

        write_his_outpatient_queue_json(HIS_QUEUE_FILE)
    return HIS_QUEUE_FILE


@lru_cache(maxsize=1)
def load_his_outpatient_queue() -> dict[str, Any]:
    path = _ensure_his_queue_file()
    return json.loads(path.read_text(encoding="utf-8"))


def reload_his_outpatient_queue() -> dict[str, Any]:
    load_his_outpatient_queue.cache_clear()
    return load_his_outpatient_queue()


def get_his_queue_summary(*, doctor_id: Optional[str] = None) -> dict[str, Any]:
    data = load_his_outpatient_queue()
    meta = data["meta"]
    if doctor_id and meta.get("doctor_id") != doctor_id:
        return {"error": f"未找到医生 {doctor_id} 的门诊队列"}
    summary = dict(data["summary"])
    summary["source"] = "his"
    summary["queue_date"] = meta.get("queue_date")
    summary["department_name"] = meta.get("department_name")
    summary["doctor_name"] = meta.get("doctor_name")
    return summary


def list_his_queue_items(
    *,
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    visit_type: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict[str, Any]]:
    data = load_his_outpatient_queue()
    meta = data["meta"]
    if doctor_id and meta.get("doctor_id") != doctor_id:
        return []

    items = list(data["items"])
    if status and status != "all":
        local = status.lower()
        his_status = {v: k for k, v in STATUS_TO_LOCAL.items()}.get(local, local.upper())
        items = [i for i in items if i["queue_status"] == his_status or STATUS_TO_LOCAL.get(i["queue_status"]) == local]
    if visit_type and visit_type != "all":
        vt = visit_type.upper()
        items = [i for i in items if i["visit_type"] == vt or i["visit_type"].lower() == visit_type.lower()]
    if search:
        q = search.strip()
        items = [
            i
            for i in items
            if q in i.get("patient_name", "") or q in i.get("chief_complaint", "")
        ]
    return sorted(items, key=lambda x: x["queue_order"])


def get_his_queue_item(slug: str) -> dict[str, Any] | None:
    for item in load_his_outpatient_queue()["items"]:
        if item["patient_slug"] == slug:
            return item
    return None


def to_patient_summary_shape(summary: dict[str, Any]) -> dict[str, int]:
    """转为 patient_summary 兼容结构，便于 Agent 统一消费。"""
    return {
        "waiting": int(summary.get("waiting", 0)),
        "consulting": int(summary.get("consulting", 0)),
        "completed": int(summary.get("completed", 0)),
        "first_visit": int(summary.get("first_visit", 0)),
        "followup": int(summary.get("followup", 0)),
    }
