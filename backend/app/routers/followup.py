from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FollowUpPlan, FollowUpTask, Patient, TaskStatus
from ..schemas import (
    FollowUpPlanCreate,
    FollowUpPlanOut,
    FollowUpPlanUpdate,
    FollowUpTaskCreate,
    FollowUpTaskOut,
    FollowUpTaskUpdate,
)
from ..services.ai_service import generate_task_result

router = APIRouter(prefix="/api/followup", tags=["followup"])

PLAN_STATUSES = {"active", "paused", "completed", "cancelled"}
TASK_STATUSES = {s.value for s in TaskStatus}


class TaskExecuteBody(BaseModel):
    note: str = ""


def _task_context(db: Session, task: FollowUpTask) -> tuple[str | None, str | None, str | None]:
    plan = db.query(FollowUpPlan).filter(FollowUpPlan.id == task.plan_id).first()
    if not plan:
        return None, None, None
    patient = db.query(Patient).filter(Patient.id == plan.patient_id).first()
    return plan.patient_id, patient.name if patient else None, plan.title


def _task_out(db: Session, task: FollowUpTask) -> FollowUpTaskOut:
    patient_id, patient_name, plan_title = _task_context(db, task)
    return FollowUpTaskOut(
        id=task.id,
        plan_id=task.plan_id,
        title=task.title,
        description=task.description,
        scheduled_at=task.scheduled_at,
        status=task.status.value,
        result=task.result,
        executed_at=task.executed_at,
        patient_id=patient_id,
        patient_name=patient_name,
        plan_title=plan_title,
    )


def _plan_out(db: Session, plan: FollowUpPlan) -> FollowUpPlanOut:
    return FollowUpPlanOut(
        id=plan.id,
        patient_id=plan.patient_id,
        doctor_id=plan.doctor_id,
        title=plan.title,
        description=plan.description,
        skill_id=plan.skill_id,
        status=plan.status,
        created_at=plan.created_at,
        tasks=[_task_out(db, t) for t in plan.tasks],
    )


def _get_plan(db: Session, plan_id: str) -> FollowUpPlan:
    plan = db.query(FollowUpPlan).filter(FollowUpPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "随访计划不存在")
    return plan


def _get_task(db: Session, task_id: str) -> FollowUpTask:
    task = db.query(FollowUpTask).filter(FollowUpTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("", response_model=list[FollowUpPlanOut])
def list_plans(patient_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(FollowUpPlan).order_by(FollowUpPlan.created_at.desc())
    if patient_id:
        q = q.filter(FollowUpPlan.patient_id == patient_id)
    return [_plan_out(db, p) for p in q.all()]


@router.post("", response_model=FollowUpPlanOut)
def create_plan(data: FollowUpPlanCreate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    plan = FollowUpPlan(
        patient_id=data.patient_id,
        doctor_id="doctor-li",
        title=data.title,
        description=data.description,
        skill_id=data.skill_id,
    )
    db.add(plan)
    db.flush()

    for task_data in data.tasks:
        db.add(
            FollowUpTask(
                plan_id=plan.id,
                title=task_data.title,
                description=task_data.description,
                scheduled_at=task_data.scheduled_at,
                status=TaskStatus.PENDING,
            )
        )

    db.commit()
    db.refresh(plan)
    return _plan_out(db, plan)


@router.put("/plans/{plan_id}", response_model=FollowUpPlanOut)
def update_plan(plan_id: str, data: FollowUpPlanUpdate, db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id)
    if data.title is not None:
        plan.title = data.title.strip()
    if data.description is not None:
        plan.description = data.description
    if data.status is not None:
        if data.status not in PLAN_STATUSES:
            raise HTTPException(400, f"无效的计划状态: {data.status}")
        plan.status = data.status
        if data.status == "cancelled":
            for task in plan.tasks:
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.CANCELLED
    db.commit()
    db.refresh(plan)
    return _plan_out(db, plan)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str, db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id)
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/tasks", response_model=FollowUpTaskOut)
def add_task(plan_id: str, data: FollowUpTaskCreate, db: Session = Depends(get_db)):
    plan = _get_plan(db, plan_id)
    if plan.status in ("cancelled", "completed"):
        raise HTTPException(400, "已结束的计划无法添加任务")

    task = FollowUpTask(
        plan_id=plan.id,
        title=data.title,
        description=data.description,
        scheduled_at=data.scheduled_at,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_out(db, task)


@router.put("/tasks/{task_id}", response_model=FollowUpTaskOut)
def update_task(task_id: str, data: FollowUpTaskUpdate, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    if data.title is not None:
        task.title = data.title.strip()
    if data.description is not None:
        task.description = data.description
    if data.scheduled_at is not None:
        task.scheduled_at = data.scheduled_at
    if data.status is not None:
        if data.status not in TASK_STATUSES:
            raise HTTPException(400, f"无效的任务状态: {data.status}")
        task.status = TaskStatus(data.status)
        if data.status == "cancelled":
            task.executed_at = None
    db.commit()
    db.refresh(task)
    return _task_out(db, task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.get("/tasks/pending", response_model=list[FollowUpTaskOut])
def pending_tasks(db: Session = Depends(get_db)):
    tasks = (
        db.query(FollowUpTask)
        .filter(FollowUpTask.status == TaskStatus.PENDING)
        .order_by(FollowUpTask.scheduled_at)
        .all()
    )
    return [_task_out(db, t) for t in tasks]


@router.post("/tasks/{task_id}/execute")
def execute_task(
    task_id: str,
    body: TaskExecuteBody | None = None,
    db: Session = Depends(get_db),
):
    task = _get_task(db, task_id)
    if task.status == TaskStatus.CANCELLED:
        raise HTTPException(400, "已取消的任务无法执行")
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(400, "任务已完成")

    plan = db.query(FollowUpPlan).filter(FollowUpPlan.id == task.plan_id).first()
    patient = (
        db.query(Patient).filter(Patient.id == plan.patient_id).first()
        if plan
        else None
    )

    note = (body.note if body else "").strip()
    result = generate_task_result(task.title, patient.name if patient else "未知")
    if note:
        result = f"{result}\n\n【医生记录】{note}"

    task.status = TaskStatus.COMPLETED
    task.executed_at = datetime.utcnow()
    task.result = result
    db.commit()
    return {"ok": True, "result": task.result}


@router.post("/tasks/{task_id}/cancel", response_model=FollowUpTaskOut)
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    task = _get_task(db, task_id)
    if task.status != TaskStatus.PENDING:
        raise HTTPException(400, "仅待执行任务可取消")
    task.status = TaskStatus.CANCELLED
    db.commit()
    db.refresh(task)
    return _task_out(db, task)
