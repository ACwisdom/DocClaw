import json



from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session



from ..database import get_db

from pydantic import BaseModel

from ..models import AgentToolExecutionLog, SkillExecutionLog
from ..services.audit_service import log_agent_tool_finish, log_agent_tool_start



router = APIRouter(prefix="/api/audit", tags=["audit"])





def _serialize_log(log: SkillExecutionLog, *, include_raw: bool = False) -> dict:

    payload = {

        "id": log.id,

        "doctor_id": log.doctor_id,

        "patient_id": log.patient_id,

        "skill_id": log.skill_id,

        "consult_message_id": log.consult_message_id,

        "task_type": log.task_type,

        "user_input": log.user_input,

        "provider": log.provider,

        "model": log.model,

        "latency_ms": log.latency_ms,

        "status": log.status,

        "created_at": log.created_at.isoformat(),

        "validation_warnings": json.loads(log.validation_warnings or "[]"),

        "field_diffs": json.loads(log.field_diffs or "[]"),

    }

    if include_raw:

        payload["input_snapshot"] = log.input_snapshot

        payload["raw_output"] = log.raw_output

        payload["structured_output"] = log.structured_output

    return payload





@router.get("/logs")

def list_audit_logs(

    patient_id: str | None = Query(default=None),

    limit: int = Query(default=20, ge=1, le=100),

    db: Session = Depends(get_db),

):

    query = db.query(SkillExecutionLog).order_by(SkillExecutionLog.created_at.desc())

    if patient_id:

        query = query.filter(SkillExecutionLog.patient_id == patient_id)

    logs = query.limit(limit).all()

    return [_serialize_log(log) for log in logs]





@router.get("/logs/{log_id}")

def get_audit_log(log_id: str, db: Session = Depends(get_db)):

    log = db.query(SkillExecutionLog).filter(SkillExecutionLog.id == log_id).first()

    if not log:

        raise HTTPException(404, "审计日志不存在")

    return _serialize_log(log, include_raw=True)


class AgentToolLogStart(BaseModel):
    doctor_id: str
    thread_id: str
    tool_name: str
    tool_call_id: str = ""
    source: str = "main"
    args_snapshot: str = ""
    patient_id: str | None = None
    patient_slug: str | None = None


class AgentToolLogFinish(BaseModel):
    thread_id: str
    tool_call_id: str
    tool_name: str
    result_text: str = ""
    status: str = "success"
    doctor_id: str | None = None
    source: str = "main"
    patient_id: str | None = None
    patient_slug: str | None = None


def _serialize_agent_tool_log(log: AgentToolExecutionLog) -> dict:
    return {
        "id": log.id,
        "doctor_id": log.doctor_id,
        "patient_id": log.patient_id,
        "thread_id": log.thread_id,
        "tool_name": log.tool_name,
        "tool_call_id": log.tool_call_id,
        "source": log.source,
        "args_snapshot": log.args_snapshot,
        "result_text": log.result_text,
        "status": log.status,
        "created_at": log.created_at.isoformat(),
        "finished_at": log.finished_at.isoformat() if log.finished_at else None,
    }


@router.get("/agent-tools")
def list_agent_tool_logs(
    thread_id: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(AgentToolExecutionLog).order_by(
        AgentToolExecutionLog.created_at.asc()
    )
    if thread_id:
        query = query.filter(AgentToolExecutionLog.thread_id == thread_id)
    if patient_id:
        query = query.filter(AgentToolExecutionLog.patient_id == patient_id)
    logs = query.limit(limit).all()
    return [_serialize_agent_tool_log(log) for log in logs]


@router.post("/agent-tools/start")
def create_agent_tool_log(body: AgentToolLogStart, db: Session = Depends(get_db)):
    entry = log_agent_tool_start(
        db,
        doctor_id=body.doctor_id,
        thread_id=body.thread_id,
        tool_name=body.tool_name,
        tool_call_id=body.tool_call_id,
        source=body.source,
        args_snapshot=body.args_snapshot,
        patient_id=body.patient_id,
        patient_slug=body.patient_slug,
    )
    db.commit()
    return _serialize_agent_tool_log(entry)


@router.post("/agent-tools/finish")
def finish_agent_tool_log(body: AgentToolLogFinish, db: Session = Depends(get_db)):
    entry = log_agent_tool_finish(
        db,
        thread_id=body.thread_id,
        tool_call_id=body.tool_call_id,
        tool_name=body.tool_name,
        result_text=body.result_text,
        status=body.status,
        doctor_id=body.doctor_id,
        source=body.source,
        patient_id=body.patient_id,
        patient_slug=body.patient_slug,
    )
    db.commit()
    return _serialize_agent_tool_log(entry)


