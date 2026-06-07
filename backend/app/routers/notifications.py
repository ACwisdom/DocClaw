from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Doctor, Notification
from ..schemas import NotificationCreate, NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db)):
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("", response_model=NotificationOut)
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    doctor_id = data.doctor_id
    if not doctor_id:
        doctor = db.query(Doctor).first()
        if not doctor:
            raise HTTPException(404, "医生信息不存在")
        doctor_id = doctor.id

    notification = Notification(
        doctor_id=doctor_id,
        title=data.title.strip(),
        content=data.content.strip(),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if n:
        n.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Notification).update({"is_read": True})
    db.commit()
    return {"ok": True}
