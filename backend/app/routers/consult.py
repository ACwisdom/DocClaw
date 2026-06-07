import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ConsultMessage, Patient, Skill, VisitStatus
from ..schemas import AgentMessageCreate, ChatRequest, MessageOut
from ..medical_record.service import normalize_structured_patient_identity
from ..services.ai_service import get_active_skill
from ..services.audit_service import attach_audit_to_message, log_skill_execution
from ..services.skill_runtime import run_skill
from ..services.skill_runtime_stream import (
    StreamSkillOutcome,
    format_sse_event,
    iter_skill_stream_events,
)

router = APIRouter(prefix="/api/consult", tags=["consult"])


def _message_payload(msg: ConsultMessage, patient: Patient | None = None) -> dict:
    out = MessageOut.model_validate(msg)
    if patient and out.structured_data:
        out.structured_data = normalize_structured_patient_identity(out.structured_data, patient)
    return out.model_dump(mode="json")


@router.get("/{slug}/messages", response_model=list[MessageOut])
def get_messages(slug: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    messages = (
        db.query(ConsultMessage)
        .filter(ConsultMessage.patient_id == patient.id)
        .order_by(ConsultMessage.created_at)
        .all()
    )
    return [_message_payload(msg, patient) for msg in messages]


@router.post("/{slug}/messages", response_model=list[MessageOut])
def send_message(slug: str, data: ChatRequest, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    if patient.status == VisitStatus.WAITING:
        patient.status = VisitStatus.CONSULTING

    history = (
        db.query(ConsultMessage)
        .filter(ConsultMessage.patient_id == patient.id)
        .order_by(ConsultMessage.created_at)
        .all()
    )

    doctor_msg = ConsultMessage(
        patient_id=patient.id, role="doctor", content=data.content,
    )
    db.add(doctor_msg)
    db.flush()

    skill = get_active_skill(db, data.skill_id)
    if skill:
        skill.usage_count += 1

    start = time.perf_counter()
    result = run_skill(db, patient, data.content, skill, history)
    latency_ms = int((time.perf_counter() - start) * 1000)

    ai_msg = ConsultMessage(
        patient_id=patient.id,
        role="assistant",
        content=result.content,
        message_type=result.message_type,
        meta_json=result.metadata,
    )
    db.add(ai_msg)
    db.flush()

    audit_log = log_skill_execution(
        db,
        patient=patient,
        skill=skill,
        result=result,
        user_input=data.content,
        latency_ms=latency_ms,
        consult_message_id=ai_msg.id,
        history=history,
    )
    if audit_log:
        attach_audit_to_message(ai_msg, audit_log, result)

    db.commit()
    db.refresh(doctor_msg)
    db.refresh(ai_msg)
    return [_message_payload(doctor_msg, patient), _message_payload(ai_msg, patient)]


@router.post("/{slug}/messages/agent", response_model=MessageOut)
def send_agent_message(slug: str, data: AgentMessageCreate, db: Session = Depends(get_db)):
    """Agent 内部写回消息，不触发 Skill Runtime。"""
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    role = data.role if data.role in ("assistant", "system") else "assistant"
    msg = ConsultMessage(
        patient_id=patient.id,
        role=role,
        content=data.content.strip(),
        message_type="text" if role == "assistant" else "system",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{slug}/messages/stream")
def send_message_stream(slug: str, data: ChatRequest, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    if patient.status == VisitStatus.WAITING:
        patient.status = VisitStatus.CONSULTING

    history = (
        db.query(ConsultMessage)
        .filter(ConsultMessage.patient_id == patient.id)
        .order_by(ConsultMessage.created_at)
        .all()
    )

    doctor_msg = ConsultMessage(
        patient_id=patient.id, role="doctor", content=data.content,
    )
    db.add(doctor_msg)
    db.flush()

    skill = get_active_skill(db, data.skill_id)
    if skill:
        skill.usage_count += 1

    def event_generator():
        yield format_sse_event("doctor_message", _message_payload(doctor_msg, patient))
        start = time.perf_counter()
        outcome: StreamSkillOutcome | None = None

        try:
            for item in iter_skill_stream_events(patient, data.content, skill, history):
                if isinstance(item, StreamSkillOutcome):
                    outcome = item
                    continue
                yield item
        except Exception as exc:
            yield format_sse_event("error", {"message": str(exc), "fallback": True})
            return

        if outcome is None:
            yield format_sse_event("error", {"message": "未生成助手回复", "fallback": True})
            return

        result = outcome.result
        latency_ms = int((time.perf_counter() - start) * 1000)

        ai_msg = ConsultMessage(
            patient_id=patient.id,
            role="assistant",
            content=result.content,
            message_type=result.message_type,
            meta_json=result.metadata,
        )
        db.add(ai_msg)
        db.flush()

        audit_log = log_skill_execution(
            db,
            patient=patient,
            skill=skill,
            result=result,
            user_input=data.content,
            latency_ms=latency_ms,
            consult_message_id=ai_msg.id,
            history=history,
        )
        if audit_log:
            attach_audit_to_message(ai_msg, audit_log, result)

        db.commit()
        db.refresh(ai_msg)
        yield format_sse_event("done", _message_payload(ai_msg, patient))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{slug}/skills")
def get_enabled_skills(slug: str, db: Session = Depends(get_db)):
    skills = db.query(Skill).filter(Skill.enabled == True).all()
    return [
        {"id": s.id, "name": s.name, "icon": s.icon, "is_default": s.is_default}
        for s in skills
    ]
