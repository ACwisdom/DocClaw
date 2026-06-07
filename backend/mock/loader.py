"""演示 Mock 数据加载器 — 从 mock/*.json 写入 SQLite。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import (
    ConsultMessage,
    Doctor,
    FollowUpPlan,
    FollowUpTask,
    Notification,
    Patient,
    Priority,
    Skill,
    SkillStatus,
    TaskStatus,
    TaskType,
    VisitStatus,
    VisitType,
)

MOCK_DIR = Path(__file__).resolve().parent


def _load_json(name: str):
    return json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def load_mock_data(db: Session) -> dict[str, int]:
    """从 JSON fixtures 写入全部演示数据，返回各实体计数。"""
    stats = {
        "doctors": 0,
        "patients": 0,
        "skills": 0,
        "consult_messages": 0,
        "followup_plans": 0,
        "followup_tasks": 0,
        "notifications": 0,
    }

    doctor_data = _load_json("doctor.json")
    db.add(Doctor(**doctor_data))
    stats["doctors"] = 1

    slug_to_patient: dict[str, Patient] = {}
    for row in _load_json("patients.json"):
        patient = Patient(
            slug=row["slug"],
            name=row["name"],
            gender=row["gender"],
            age=row["age"],
            chief_complaint=row["chief_complaint"],
            visit_type=VisitType(row["visit_type"]),
            status=VisitStatus(row["status"]),
            priority=Priority(row["priority"]),
            queue_order=row["queue_order"],
            completed_exams=row.get("completed_exams", ""),
            key_notes=row.get("key_notes", ""),
            first_visit_note=row.get("first_visit_note", ""),
        )
        db.add(patient)
        slug_to_patient[row["slug"]] = patient
        stats["patients"] += 1

    for row in _load_json("skills.json"):
        db.add(
            Skill(
                id=row["id"],
                doctor_id=row["doctor_id"],
                name=row["name"],
                description=row["description"],
                version=row.get("version", "v1.0"),
                mode=row.get("mode", ""),
                system_prompt=row.get("system_prompt", ""),
                tags=row.get("tags", ""),
                status=SkillStatus(row["status"]),
                task_type=TaskType(row["task_type"]),
                enabled=row.get("enabled", False),
                is_default=row.get("is_default", False),
                rating=row.get("rating", 0.0),
                usage_count=row.get("usage_count", 0),
                review_count=row.get("review_count", 0),
                icon=row.get("icon", "description"),
                created_at=_parse_dt(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
                published_to_store=row.get("published_to_store", False),
            )
        )
        stats["skills"] += 1

    db.flush()

    consult_cfg = _load_json("consult_messages.json")
    demo_slug = consult_cfg["demo_patient_slug"]
    demo_patient = slug_to_patient.get(demo_slug)
    demo_name = demo_patient.name if demo_patient else "王浩然"

    if demo_patient:
        for msg in consult_cfg["messages"]:
            content = msg["content"].format(demo_name=demo_name)
            db.add(
                ConsultMessage(
                    patient_id=demo_patient.id,
                    role=msg["role"],
                    message_type=msg.get("message_type", "text"),
                    content=content,
                )
            )
            stats["consult_messages"] += 1

    followup_cfg = _load_json("followup.json")
    followup_patient = slug_to_patient.get(followup_cfg["demo_patient_slug"])
    if followup_patient:
        plan_cfg = followup_cfg["plan"]
        plan = FollowUpPlan(
            patient_id=followup_patient.id,
            doctor_id=followup_cfg["doctor_id"],
            title=f"{demo_name} - {plan_cfg['title_suffix']}",
            description=plan_cfg["description"],
            skill_id=plan_cfg.get("skill_id"),
            created_at=datetime.utcnow()
            + timedelta(
                days=plan_cfg.get("created_at_offset_days", 0),
                hours=plan_cfg.get("created_at_offset_hours", 0),
                minutes=plan_cfg.get("created_at_offset_minutes", 0),
            ),
        )
        db.add(plan)
        db.flush()
        stats["followup_plans"] = 1

        for task_cfg in followup_cfg["tasks"]:
            db.add(
                FollowUpTask(
                    plan_id=plan.id,
                    title=task_cfg["title"],
                    description=task_cfg.get("description", ""),
                    scheduled_at=datetime.utcnow()
                    + timedelta(
                        days=task_cfg.get("scheduled_at_offset_days", 0),
                        hours=task_cfg.get("scheduled_at_offset_hours", 0),
                        minutes=task_cfg.get("scheduled_at_offset_minutes", 0),
                        seconds=task_cfg.get("scheduled_at_offset_seconds", 0),
                    ),
                    status=TaskStatus(task_cfg.get("status", "pending")),
                )
            )
            stats["followup_tasks"] += 1

    for row in _load_json("notifications.json"):
        db.add(
            Notification(
                doctor_id=row["doctor_id"],
                title=row["title"],
                content=row["content"].format(demo_name=demo_name),
            )
        )
        stats["notifications"] += 1

    db.commit()
    return stats


def bootstrap_preferences(doctor_id: str = "doctor-li") -> Path:
    """将 mock/preferences.md 复制到 agent_workspace/memories/{doctor_id}/。"""
    from agent.config import LOCAL_WORKSPACE_DIR

    src = MOCK_DIR / "preferences.md"
    dest_dir = LOCAL_WORKSPACE_DIR / "memories" / doctor_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "preferences.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def expected_patient_summary() -> dict[str, int]:
    """根据 fixtures 计算预期的队列统计（PatientSummary 派生值）。"""
    patients = _load_json("patients.json")
    return {
        "waiting": sum(1 for p in patients if p["status"] == "waiting"),
        "consulting": sum(1 for p in patients if p["status"] == "consulting"),
        "completed": sum(1 for p in patients if p["status"] == "completed"),
        "first_visit": sum(1 for p in patients if p["visit_type"] == "first"),
        "followup": sum(1 for p in patients if p["visit_type"] == "followup"),
    }
