from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Doctor, Patient, VisitStatus, VisitType
from ..schemas import DoctorOut, PatientOut, PatientSummary

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
def list_patients(
    status: Optional[str] = None,
    visit_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Patient).order_by(Patient.queue_order)
    if status and status != "all":
        q = q.filter(Patient.status == VisitStatus(status))
    if visit_type and visit_type != "all":
        q = q.filter(Patient.visit_type == VisitType(visit_type))
    if search:
        q = q.filter(
            (Patient.name.contains(search)) | (Patient.chief_complaint.contains(search))
        )
    return q.all()


@router.get("/summary", response_model=PatientSummary)
def patient_summary(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()
    return PatientSummary(
        waiting=sum(1 for p in patients if p.status == VisitStatus.WAITING),
        consulting=sum(1 for p in patients if p.status == VisitStatus.CONSULTING),
        completed=sum(1 for p in patients if p.status == VisitStatus.COMPLETED),
        first_visit=sum(1 for p in patients if p.visit_type == VisitType.FIRST),
        followup=sum(1 for p in patients if p.visit_type == VisitType.FOLLOWUP),
    )


@router.get("/{slug}", response_model=PatientOut)
def get_patient(slug: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    return patient


@router.post("/{slug}/start")
def start_consultation(slug: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    if patient.status == VisitStatus.WAITING:
        patient.status = VisitStatus.CONSULTING
        db.commit()
    return {"ok": True, "status": patient.status.value}


@router.post("/{slug}/complete")
def complete_consultation(slug: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.slug == slug).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    patient.status = VisitStatus.COMPLETED
    db.commit()
    return {"ok": True}


@router.get("/doctor/me", response_model=DoctorOut)
def get_current_doctor(db: Session = Depends(get_db)):
    doctor = db.query(Doctor).first()
    if not doctor:
        raise HTTPException(404, "医生信息不存在")
    return doctor
