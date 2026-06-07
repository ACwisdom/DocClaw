"""门诊队列数据获取 — API 优先，演示环境 mock 降级。"""

from __future__ import annotations

import re

import httpx

from agent.env_utils import MEDICAL_API_BASE_URL

# 与 mock/patients.json 一致的演示默认值
DEFAULT_MOCK_SUMMARY: dict[str, int] = {
    "waiting": 9,
    "consulting": 1,
    "completed": 10,
    "first_visit": 11,
    "followup": 9,
}

_QUEUE_QUERY_RE = re.compile(
    r"待接诊|候诊|排队.*(多少|几)|多少.*(待|候)诊|几.*(位|个|名).*待诊|"
    r"今天.*(多少|几).*(患者|接诊|排队)|今日队列|接诊.*(统计|情况|人数|多少)",
    re.IGNORECASE,
)


def mock_patient_summary() -> dict[str, int]:
    try:
        from mock.loader import expected_patient_summary

        return expected_patient_summary()
    except Exception:
        return dict(DEFAULT_MOCK_SUMMARY)


def is_queue_summary_query(message: str | None) -> bool:
    if not message or not message.strip():
        return False
    return bool(_QUEUE_QUERY_RE.search(message.strip()))


def _his_summary_to_shape(data: dict) -> dict:
    return {
        "waiting": int(data.get("waiting", 0)),
        "consulting": int(data.get("consulting", 0)),
        "completed": int(data.get("completed", 0)),
        "first_visit": int(data.get("first_visit", 0)),
        "followup": int(data.get("followup", 0)),
    }


async def fetch_patient_summary() -> dict:
    """优先读 HIS 门诊队列，其次 Medical API patients/summary，最后 mock。"""
    his_url = f"{MEDICAL_API_BASE_URL.rstrip('/')}/his/outpatient/queue/summary"
    api_url = f"{MEDICAL_API_BASE_URL.rstrip('/')}/patients/summary"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in (his_url, api_url):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    if isinstance(data, dict) and "waiting" in data:
                        if url == his_url:
                            extra = {
                                k: data[k]
                                for k in ("queue_date", "department_name", "doctor_name", "source")
                                if k in data
                            }
                            return {**_his_summary_to_shape(data), "source": "his", **extra}
                        return data
                except Exception:
                    continue
    except Exception:
        pass
    return mock_patient_summary()


def format_queue_summary_reply(summary: dict, *, doctor_name: str = "医生") -> str:
    waiting = summary.get("waiting", 0)
    consulting = summary.get("consulting", 0)
    completed = summary.get("completed", 0)
    return (
        f"{doctor_name}您好，今日门诊队列概况如下：\n\n"
        f"- **待接诊**：{waiting} 人\n"
        f"- **问诊中**：{consulting} 人\n"
        f"- **已完成**：{completed} 人\n\n"
        f"如需查看某位患者详情，直接告诉我姓名即可。"
    )
