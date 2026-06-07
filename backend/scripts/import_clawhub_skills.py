"""CLI: import ClawHub skills into DocClaw skill plaza."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, Base, engine, migrate_schema
from app.services.clawhub_client import DEFAULT_MEDICAL_SLUGS
from app.services.clawhub_importer import import_clawhub_skill, setup_clawhub_plaza


def main() -> None:
    parser = argparse.ArgumentParser(description="从 ClawHub 导入技能到 DocClaw 技能广场")
    parser.add_argument("--slug", action="append", help="指定 ClawHub slug，可重复")
    parser.add_argument("--force", action="store_true", help="强制更新已存在的技能")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        slugs = args.slug or DEFAULT_MEDICAL_SLUGS
        if args.slug:
            imported = [
                s for slug in slugs
                if (s := import_clawhub_skill(db, slug, force_update=args.force))
            ]
        else:
            imported = setup_clawhub_plaza(db, force_update=args.force)
        print(f"成功导入/更新 {len(imported)} 个 ClawHub 技能:")
        for skill in imported:
            print(f"  - {skill.name} ({skill.clawhub_slug})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
