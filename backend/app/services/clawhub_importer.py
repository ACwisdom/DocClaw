"""Import ClawHub skills into DocClaw skill plaza (StoreSkill)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..models import StoreSkill
from .clawhub_client import DEFAULT_MEDICAL_SLUGS, ClawHubClient, ParsedClawHubSkill

SKILLS_CACHE_DIR = Path(__file__).resolve().parents[2] / "skills" / "clawhub"


FEATURED_SLUG = "clinical-doc-assistant"
EDITORS_CHOICE_SLUGS = ("medical-qa", "clinical-doc-assistant", "pubmed-literature-search")


def purge_non_clawhub_store_skills(db: Session) -> int:
    """Remove demo/local plaza entries; keep only ClawHub imports."""
    rows = db.query(StoreSkill).filter(
        (StoreSkill.source != "clawhub") | (StoreSkill.clawhub_slug.is_(None))
    ).all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    if count:
        db.commit()
    return count


def configure_plaza_highlights(db: Session) -> None:
    for row in db.query(StoreSkill).all():
        row.is_featured = row.clawhub_slug == FEATURED_SLUG
        row.is_editors_choice = row.clawhub_slug in EDITORS_CHOICE_SLUGS
    db.commit()


def setup_clawhub_plaza(db: Session, *, force_update: bool = False) -> list[StoreSkill]:
    """技能广场仅保留 ClawHub 医疗技能，并设置推荐/精选。"""
    from .clawhub_localizations import apply_localizations_to_db

    purge_non_clawhub_store_skills(db)
    imported = import_default_clawhub_skills(db, force_update=force_update)
    apply_localizations_to_db(db)
    configure_plaza_highlights(db)
    return imported


def dedupe_clawhub_store_skills(db: Session) -> int:
    """Remove duplicate ClawHub entries, keeping the newest row per slug."""
    rows = (
        db.query(StoreSkill)
        .filter(StoreSkill.clawhub_slug.isnot(None))
        .order_by(StoreSkill.updated_at.desc())
        .all()
    )
    seen: set[str] = set()
    removed = 0
    for row in rows:
        slug = row.clawhub_slug or ""
        if slug in seen:
            db.delete(row)
            removed += 1
        else:
            seen.add(slug)
    if removed:
        db.commit()
    return removed


def _store_skill_from_parsed(parsed: ParsedClawHubSkill) -> StoreSkill:
    return StoreSkill(
        name=parsed.name,
        author=parsed.author,
        description=parsed.description,
        category=parsed.category,
        version=parsed.version,
        tags=f"ClawHub,{parsed.tags}",
        install_count=parsed.install_count,
        rating=parsed.rating,
        scenarios=parsed.scenarios,
        compatibility=parsed.compatibility,
        highlights=parsed.highlights,
        publisher=parsed.publisher,
        updated_at=parsed.updated_at,
        system_prompt=parsed.system_prompt,
        clawhub_slug=parsed.slug,
        source="clawhub",
        is_editors_choice=parsed.slug in EDITORS_CHOICE_SLUGS,
    )


def import_clawhub_skill(
    db: Session,
    slug: str,
    *,
    client: ClawHubClient | None = None,
    save_files: bool = True,
    force_update: bool = False,
) -> StoreSkill | None:
    existing = db.query(StoreSkill).filter(StoreSkill.clawhub_slug == slug).first()
    if existing and not force_update:
        return existing

    client = client or ClawHubClient()
    save_dir = SKILLS_CACHE_DIR / slug if save_files else None
    try:
        parsed = client.fetch_parsed_skill(slug, save_dir=save_dir)
    except Exception as exc:
        print(f"[clawhub] skip {slug}: {exc}")
        return None

    if existing:
        existing.name = parsed.name
        existing.author = parsed.author
        existing.description = parsed.description
        existing.category = parsed.category
        existing.version = parsed.version
        existing.tags = f"ClawHub,{parsed.tags}"
        existing.install_count = parsed.install_count
        existing.rating = parsed.rating
        existing.scenarios = parsed.scenarios
        existing.compatibility = parsed.compatibility
        existing.highlights = parsed.highlights
        existing.publisher = parsed.publisher
        existing.updated_at = parsed.updated_at
        existing.system_prompt = parsed.system_prompt
        existing.source = "clawhub"
        existing.clawhub_slug = parsed.slug
        db.commit()
        db.refresh(existing)
        return existing

    skill = _store_skill_from_parsed(parsed)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def import_default_clawhub_skills(
    db: Session,
    slugs: list[str] | None = None,
    *,
    force_update: bool = False,
) -> list[StoreSkill]:
    dedupe_clawhub_store_skills(db)
    slugs = slugs or DEFAULT_MEDICAL_SLUGS
    client = ClawHubClient()
    imported: list[StoreSkill] = []
    for slug in slugs:
        skill = import_clawhub_skill(db, slug, client=client, force_update=force_update)
        if skill:
            imported.append(skill)
    dedupe_clawhub_store_skills(db)
    return imported
