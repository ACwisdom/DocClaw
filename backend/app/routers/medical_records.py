import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..medical_record.service import normalize_structured_patient_identity
from ..models import ConsultMessage, Doctor, Patient, SkillExecutionLog
from ..schemas import MedicalRecordConfirm, MessageOut

router = APIRouter(prefix="/api/medical-records", tags=["medical-records"])


@router.post("/{slug}/confirm", response_model=MessageOut)
def confirm_medical_record(
    slug: str,
    data: MedicalRecordConfirm,
    db: Session = Depends(get_db),
):
    """HITL 确认后写入正式病历（Agent / MCP his_write_record 调用）。"""
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    meta: dict = {"source": "agent_harness", "confirmed": True}
    if data.structured_data:
        meta["structured_data"] = normalize_structured_patient_identity(
            data.structured_data, patient
        )

    msg = ConsultMessage(
        patient_id=patient.id,
        role="assistant",
        content=data.content.strip(),
        message_type="medical_record",
        meta_json=json.dumps(meta, ensure_ascii=False),
    )
    db.add(msg)
    db.flush()

    doctor = db.query(Doctor).first()
    if not doctor:
        raise HTTPException(404, "医生信息不存在")

    audit_log = SkillExecutionLog(
        doctor_id=doctor.id,
        patient_id=patient.id,
        skill_id=None,
        consult_message_id=msg.id,
        task_type="realtime",
        user_input="[HITL confirm]",
        provider="agent_harness",
        model="",
        latency_ms=0,
        status="confirmed",
        structured_output=json.dumps(meta.get("structured_data") or {}, ensure_ascii=False),
    )
    db.add(audit_log)
    db.commit()
    db.refresh(msg)
    return msg
