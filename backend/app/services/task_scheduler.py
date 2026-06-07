from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import FollowUpPlan, FollowUpTask, Notification, Patient, TaskStatus
from ..services.ai_service import generate_task_result


scheduler = BackgroundScheduler()


def execute_pending_tasks():
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        tasks = (
            db.query(FollowUpTask)
            .filter(
                FollowUpTask.status == TaskStatus.PENDING,
                FollowUpTask.scheduled_at <= now,
            )
            .all()
        )
        for task in tasks:
            task.status = TaskStatus.RUNNING
            db.flush()
            plan = db.query(FollowUpPlan).filter(FollowUpPlan.id == task.plan_id).first()
            patient = (
                db.query(Patient).filter(Patient.id == plan.patient_id).first()
                if plan else None
            )
            patient_name = patient.name if patient else "未知患者"
            task.result = generate_task_result(task.title, patient_name)
            task.status = TaskStatus.COMPLETED
            task.executed_at = now
            if plan:
                db.add(
                    Notification(
                        doctor_id=plan.doctor_id,
                        title=f"随访任务已执行：{task.title}",
                        content=(
                            f"患者 {patient_name} 的随访任务已自动完成。\n"
                            f"计划：{plan.title}\n"
                            f"结果摘要：{task.result[:300]}"
                        ),
                    )
                )
        db.commit()
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(execute_pending_tasks, "interval", minutes=1, id="followup_tasks")
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
