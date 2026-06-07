import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (
    AgentToolExecutionLog,
    ConsultMessage,
    Doctor,
    Patient,
    Skill,
    SkillExecutionLog,
)
from ..services.skill_runtime import SkillRunResult, build_patient_context
from ..medical_record.service import summarize_conversation


def _resolve_doctor_id(db: Session, skill: Skill | None) -> str:
    if skill and skill.doctor_id:
        return skill.doctor_id
    doctor = db.query(Doctor).first()
    if not doctor:
        raise RuntimeError("未找到医生账号")
    return doctor.id


def attach_audit_to_message(
    ai_msg: ConsultMessage,
    audit_log: SkillExecutionLog,
    result: SkillRunResult,
) -> None:
    meta: dict = {}
    if ai_msg.meta_json:
        try:
            meta = json.loads(ai_msg.meta_json)
        except json.JSONDecodeError:
            meta = {}
    elif result.metadata:
        try:
            meta = json.loads(result.metadata)
        except json.JSONDecodeError:
            meta = {}

    meta["audit_log_id"] = audit_log.id
    if result.field_diffs:
        meta["field_diffs"] = result.field_diffs
    ai_msg.meta_json = json.dumps(meta, ensure_ascii=False)


def log_skill_execution(
    db: Session,
    *,
    patient: Patient,
    skill: Skill | None,
    result: SkillRunResult,
    user_input: str,
    latency_ms: int,
    consult_message_id: str | None = None,
    history: list[ConsultMessage] | None = None,
    status: str | None = None,
) -> SkillExecutionLog | None:
    if not skill and result.message_type != "medical_record":
        return None

    history = history or []
    doctor_id = _resolve_doctor_id(db, skill)
    task_type = skill.task_type.value if skill else "realtime"
    execution_status = status or ("fallback" if result.used_fallback else "success")
    if result.message_type == "medical_record" and result.used_fallback and execution_status == "success":
        execution_status = "fallback"

    input_snapshot = json.dumps(
        {
            "patient_context": build_patient_context(patient),
            "conversation_summary": summarize_conversation(history, user_input),
        },
        ensure_ascii=False,
    )
    structured_output = ""
    if result.structured_data:
        structured_output = json.dumps(result.structured_data, ensure_ascii=False)

    audit_log = SkillExecutionLog(
        doctor_id=doctor_id,
        patient_id=patient.id,
        skill_id=skill.id if skill else None,
        consult_message_id=consult_message_id,
        task_type=task_type,
        user_input=user_input,
        provider=result.provider,
        model=result.model or "",
        latency_ms=latency_ms,
        status=execution_status,
        input_snapshot=input_snapshot,
        raw_output=result.raw_output or result.content,
        structured_output=structured_output,
        validation_warnings=json.dumps(result.validation_warnings, ensure_ascii=False),
        field_diffs=json.dumps(result.field_diffs, ensure_ascii=False),
    )
    db.add(audit_log)
    db.flush()
    return audit_log


def resolve_patient_id(db: Session, *, patient_id: str | None, patient_slug: str | None) -> str | None:
    if patient_id:
        return patient_id
    if not patient_slug:
        return None
    patient = db.query(Patient).filter(Patient.slug == patient_slug).first()
    return patient.id if patient else None


def log_agent_tool_start(
    db: Session,
    *,
    doctor_id: str,
    thread_id: str,
    tool_name: str,
    tool_call_id: str = "",
    source: str = "main",
    args_snapshot: str = "",
    patient_id: str | None = None,
    patient_slug: str | None = None,
) -> AgentToolExecutionLog:
    resolved_patient = resolve_patient_id(
        db, patient_id=patient_id, patient_slug=patient_slug
    )
    entry = AgentToolExecutionLog(
        doctor_id=doctor_id,
        patient_id=resolved_patient,
        thread_id=thread_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        source=source,
        args_snapshot=args_snapshot[:4000],
        status="calling",
    )
    db.add(entry)
    db.flush()
    return entry


def log_agent_tool_finish(
    db: Session,
    *,
    thread_id: str,
    tool_call_id: str,
    tool_name: str,
    result_text: str = "",
    status: str = "success",
    doctor_id: str | None = None,
    source: str = "main",
    patient_id: str | None = None,
    patient_slug: str | None = None,
) -> AgentToolExecutionLog:
    query = db.query(AgentToolExecutionLog).filter(
        AgentToolExecutionLog.thread_id == thread_id,
        AgentToolExecutionLog.tool_call_id == tool_call_id,
        AgentToolExecutionLog.status == "calling",
    )
    entry = query.order_by(AgentToolExecutionLog.created_at.desc()).first()

    if entry is None:
        entry = log_agent_tool_start(
            db,
            doctor_id=doctor_id or "doctor-li",
            thread_id=thread_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            source=source,
            patient_id=patient_id,
            patient_slug=patient_slug,
        )

    entry.result_text = result_text[:8000]
    entry.status = status
    entry.finished_at = datetime.utcnow()
    db.flush()
    return entry
