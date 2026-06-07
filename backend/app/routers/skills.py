from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Patient, Skill, SkillStatus, TaskType
from ..schemas import SkillCreate, SkillOut, SkillStats, SkillUpdate

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _skill_out(skill: Skill, doctor_name: str = "") -> SkillOut:
    return SkillOut(
        id=skill.id,
        doctor_id=skill.doctor_id,
        name=skill.name,
        description=skill.description,
        version=skill.version,
        mode=skill.mode,
        input_desc=skill.input_desc,
        output_desc=skill.output_desc,
        system_prompt=skill.system_prompt,
        tags=skill.tags,
        status=skill.status.value,
        task_type=skill.task_type.value,
        enabled=skill.enabled,
        is_default=skill.is_default,
        rating=skill.rating,
        usage_count=skill.usage_count,
        review_count=skill.review_count,
        icon=skill.icon,
        created_at=skill.created_at,
        published_to_store=skill.published_to_store,
        doctor_name=doctor_name,
    )


@router.get("", response_model=list[SkillOut])
def list_skills(db: Session = Depends(get_db)):
    skills = db.query(Skill).order_by(Skill.created_at.desc()).all()
    result = []
    for s in skills:
        doctor_name = s.doctor.name if s.doctor else "平台"
        result.append(_skill_out(s, doctor_name))
    return result


@router.get("/stats", response_model=SkillStats)
def skill_stats(db: Session = Depends(get_db)):
    skills = db.query(Skill).all()
    return SkillStats(
        enabled=sum(1 for s in skills if s.enabled and not s.is_default),
        draft=sum(1 for s in skills if s.status == SkillStatus.DRAFT),
        published=sum(1 for s in skills if s.published_to_store or s.status == SkillStatus.PUBLISHED),
        default=sum(1 for s in skills if s.is_default),
    )


@router.get("/{skill_id}", response_model=SkillOut)
def get_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    return _skill_out(skill, skill.doctor.name if skill.doctor else "平台")


@router.post("", response_model=SkillOut)
def create_skill(data: SkillCreate, db: Session = Depends(get_db)):
    skill = Skill(
        doctor_id="doctor-li",
        name=data.name,
        description=data.description,
        input_desc=data.input_desc,
        output_desc=data.output_desc,
        system_prompt=data.system_prompt,
        mode=data.mode,
        tags=data.tags,
        task_type=TaskType(data.task_type),
        icon=data.icon,
        status=SkillStatus.DRAFT,
        enabled=False,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return _skill_out(skill, "李医生")


@router.put("/{skill_id}", response_model=SkillOut)
def update_skill(skill_id: str, data: SkillUpdate, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    if skill.is_default:
        raise HTTPException(400, "默认技能不可编辑")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "status" and value:
            setattr(skill, field, SkillStatus(value))
        else:
            setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return _skill_out(skill, skill.doctor.name if skill.doctor else "李医生")


@router.post("/{skill_id}/toggle")
def toggle_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    if skill.is_default:
        raise HTTPException(400, "默认技能不可停用")
    skill.enabled = not skill.enabled
    if skill.enabled and skill.status == SkillStatus.DRAFT:
        skill.status = SkillStatus.ENABLED
    db.commit()
    return {"enabled": skill.enabled}


@router.post("/{skill_id}/publish")
def publish_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    skill.published_to_store = True
    skill.status = SkillStatus.PUBLISHED
    db.commit()
    return {"ok": True}


@router.delete("/{skill_id}")
def delete_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    if skill.is_default:
        raise HTTPException(400, "默认技能不可删除")
    db.delete(skill)
    db.commit()
    return {"ok": True}
