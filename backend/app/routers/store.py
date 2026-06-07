from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Skill, SkillStatus, StoreSkill, TaskType
from ..schemas import SkillOut, StoreSkillOut
from ..services.clawhub_importer import setup_clawhub_plaza

router = APIRouter(prefix="/api/store", tags=["store"])


class ClawHubSyncResult(BaseModel):
    imported: int
    slugs: list[str]


@router.post("/sync-clawhub", response_model=ClawHubSyncResult)
def sync_clawhub_skills(db: Session = Depends(get_db)):
    """从 ClawHub 拉取医疗相关技能并同步到技能广场。"""
    skills = setup_clawhub_plaza(db, force_update=True)
    return ClawHubSyncResult(
        imported=len(skills),
        slugs=[s.clawhub_slug for s in skills if s.clawhub_slug],
    )


@router.get("", response_model=list[StoreSkillOut])
def list_store_skills(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(StoreSkill).order_by(StoreSkill.install_count.desc())
    if category and category != "all":
        q = q.filter(StoreSkill.category == category)
    if search:
        q = q.filter(
            (StoreSkill.name.contains(search)) | (StoreSkill.description.contains(search))
        )
    return q.all()


@router.get("/featured", response_model=StoreSkillOut)
def featured_skill(db: Session = Depends(get_db)):
    skill = db.query(StoreSkill).filter(StoreSkill.is_featured == True).first()
    if not skill:
        skill = db.query(StoreSkill).first()
    if not skill:
        raise HTTPException(404, "暂无推荐技能")
    return skill


@router.get("/editors-choice", response_model=list[StoreSkillOut])
def editors_choice(db: Session = Depends(get_db)):
    return db.query(StoreSkill).filter(StoreSkill.is_editors_choice == True).all()


@router.get("/{skill_id}", response_model=StoreSkillOut)
def get_store_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(StoreSkill).filter(StoreSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(404, "技能不存在")
    return skill


@router.post("/{skill_id}/install", response_model=SkillOut)
def install_skill(skill_id: str, db: Session = Depends(get_db)):
    store_skill = db.query(StoreSkill).filter(StoreSkill.id == skill_id).first()
    if not store_skill:
        raise HTTPException(404, "技能不存在")

    existing = db.query(Skill).filter(Skill.store_skill_id == skill_id).first()
    if existing:
        return SkillOut(
            id=existing.id, doctor_id=existing.doctor_id, name=existing.name,
            description=existing.description, version=existing.version,
            mode=existing.mode, input_desc=existing.input_desc,
            output_desc=existing.output_desc, system_prompt=existing.system_prompt,
            tags=existing.tags, status=existing.status.value,
            task_type=existing.task_type.value, enabled=existing.enabled,
            is_default=existing.is_default, rating=existing.rating,
            usage_count=existing.usage_count, review_count=existing.review_count,
            icon="download", created_at=existing.created_at,
            published_to_store=existing.published_to_store, doctor_name="李医生",
        )

    store_skill.install_count += 1
    skill = Skill(
        doctor_id="doctor-li",
        name=store_skill.name,
        description=store_skill.description,
        system_prompt=store_skill.system_prompt or f"你是{store_skill.name}。{store_skill.description}",
        input_desc=store_skill.input_desc,
        output_desc=store_skill.output_desc,
        tags=store_skill.tags,
        status=SkillStatus.ENABLED,
        task_type=TaskType.REALTIME,
        enabled=True,
        store_skill_id=skill_id,
        rating=store_skill.rating,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return SkillOut(
        id=skill.id, doctor_id=skill.doctor_id, name=skill.name,
        description=skill.description, version=skill.version,
        mode=skill.mode, input_desc=skill.input_desc,
        output_desc=skill.output_desc, system_prompt=skill.system_prompt,
        tags=skill.tags, status=skill.status.value,
        task_type=skill.task_type.value, enabled=skill.enabled,
        is_default=skill.is_default, rating=skill.rating,
        usage_count=skill.usage_count, review_count=skill.review_count,
        icon="download", created_at=skill.created_at,
        published_to_store=skill.published_to_store, doctor_name="李医生",
    )
