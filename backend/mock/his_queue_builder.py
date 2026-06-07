"""从 patients.json / doctor.json 生成 HIS 门诊队列 mock 数据。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

MOCK_DIR = Path(__file__).resolve().parent

STATUS_MAP = {
    "waiting": "WAITING",
    "consulting": "IN_CONSULT",
    "completed": "COMPLETED",
}
VISIT_MAP = {"first": "FIRST", "followup": "FOLLOWUP"}
PRIORITY_MAP = {"urgent": "URGENT", "normal": "NORMAL", "chronic": "CHRONIC"}
GENDER_MAP = {"男": "M", "女": "F"}


def build_his_outpatient_queue(*, queue_date: str | None = None) -> dict:
    doctor = json.loads((MOCK_DIR / "doctor.json").read_text(encoding="utf-8"))
    patients = json.loads((MOCK_DIR / "patients.json").read_text(encoding="utf-8"))
    today = queue_date or date.today().isoformat()
    base_dt = datetime.fromisoformat(f"{today}T08:00:00")

    items = []
    for p in sorted(patients, key=lambda x: x["queue_order"]):
        order = p["queue_order"]
        reg_dt = base_dt + timedelta(minutes=(order - 1) * 12)
        called_dt = reg_dt + timedelta(minutes=8) if p["status"] == "consulting" else None
        completed_dt = reg_dt + timedelta(minutes=25) if p["status"] == "completed" else None
        items.append(
            {
                "registration_id": f"REG-{today.replace('-', '')}-{order:03d}",
                "queue_number": f"A{order:03d}",
                "patient_slug": p["slug"],
                "patient_id_his": f"HIS-P-{10000 + order}",
                "patient_name": p["name"],
                "gender": GENDER_MAP.get(p["gender"], p["gender"]),
                "age": p["age"],
                "visit_type": VISIT_MAP.get(p["visit_type"], p["visit_type"].upper()),
                "queue_status": STATUS_MAP.get(p["status"], p["status"].upper()),
                "priority": PRIORITY_MAP.get(p["priority"], p["priority"].upper()),
                "chief_complaint": p["chief_complaint"],
                "queue_order": order,
                "registered_at": reg_dt.isoformat(timespec="seconds"),
                "called_at": called_dt.isoformat(timespec="seconds") if called_dt else None,
                "completed_at": completed_dt.isoformat(timespec="seconds") if completed_dt else None,
                "room": "呼吸内科门诊 3 诊室",
            }
        )

    summary = {
        "waiting": sum(1 for p in patients if p["status"] == "waiting"),
        "consulting": sum(1 for p in patients if p["status"] == "consulting"),
        "completed": sum(1 for p in patients if p["status"] == "completed"),
        "total": len(patients),
        "first_visit": sum(1 for p in patients if p["visit_type"] == "first"),
        "followup": sum(1 for p in patients if p["visit_type"] == "followup"),
    }

    return {
        "meta": {
            "system": "DocClaw-HIS-Mock",
            "interface": "OutpatientQueue/v1",
            "hospital_id": "HOSP-DEMO-001",
            "hospital_name": "演示医疗中心",
            "department_code": "RESP-OPD",
            "department_name": doctor["department"],
            "doctor_id": doctor["id"],
            "doctor_name": doctor["name"],
            "queue_date": today,
            "updated_at": datetime.now().replace(microsecond=0).isoformat(),
        },
        "summary": summary,
        "items": items,
    }


def write_his_outpatient_queue_json(path: Path | None = None) -> Path:
    path = path or (MOCK_DIR / "his_outpatient_queue.json")
    payload = build_his_outpatient_queue()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = write_his_outpatient_queue_json()
    print(f"已生成 {out}")
