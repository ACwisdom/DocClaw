"""重置并加载 DocClaw 演示 Mock 数据。

用法:
    cd backend
    py -3.11 scripts/seed_mock.py --reset
    py -3.11 scripts/seed_mock.py --reset --with-clawhub
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保 backend 在 sys.path 中
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def reset_database() -> None:
    """清空全部演示表并重建 schema。"""
    from sqlalchemy import inspect, text

    from app.database import Base, SQLALCHEMY_DATABASE_URL, SessionLocal, engine, migrate_schema

    engine.dispose()

    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    db_file = BACKEND_DIR / db_path

    if db_file.exists():
        try:
            db_file.unlink()
            Base.metadata.create_all(bind=engine)
            migrate_schema()
            return
        except OSError:
            pass

    # 数据库文件被占用时，逐表清空
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in tables:
            conn.execute(text(f'DELETE FROM "{table}"'))
        conn.execute(text("PRAGMA foreign_keys = ON"))

    Base.metadata.create_all(bind=engine)
    migrate_schema()

    db = SessionLocal()
    try:
        db.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


def seed_mock(*, with_clawhub: bool = False) -> dict:
    from app.database import SessionLocal
    from mock.loader import bootstrap_preferences, expected_patient_summary, load_mock_data

    db = SessionLocal()
    try:
        stats = load_mock_data(db)
    finally:
        db.close()

    if with_clawhub:
        from app.services.clawhub_importer import setup_clawhub_plaza

        db = SessionLocal()
        try:
            setup_clawhub_plaza(db)
        finally:
            db.close()

    prefs_path = bootstrap_preferences("doctor-li")
    from mock.his_queue_builder import write_his_outpatient_queue_json

    his_queue_path = write_his_outpatient_queue_json()
    summary = expected_patient_summary()

    return {
        "stats": stats,
        "preferences_path": str(prefs_path),
        "his_queue_path": str(his_queue_path),
        "patient_summary": summary,
    }


def verify_summary() -> dict:
    """直接查询数据库验证 PatientSummary 派生值。"""
    from app.database import SessionLocal
    from app.models import Patient, VisitStatus, VisitType

    db = SessionLocal()
    try:
        patients = db.query(Patient).all()
        return {
            "waiting": sum(1 for p in patients if p.status == VisitStatus.WAITING),
            "consulting": sum(1 for p in patients if p.status == VisitStatus.CONSULTING),
            "completed": sum(1 for p in patients if p.status == VisitStatus.COMPLETED),
            "first_visit": sum(1 for p in patients if p.visit_type == VisitType.FIRST),
            "followup": sum(1 for p in patients if p.visit_type == VisitType.FOLLOWUP),
            "total": len(patients),
        }
    finally:
        db.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="重置并加载 DocClaw 演示 Mock 数据")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="清空数据库后重新写入 mock 数据（推荐）",
    )
    parser.add_argument(
        "--with-clawhub",
        action="store_true",
        help="同时导入 ClawHub 广场技能（store_skills）",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅验证当前数据库中的队列统计",
    )
    args = parser.parse_args()

    if args.verify_only:
        summary = verify_summary()
        print("\n=== 当前队列统计 ===")
        for key, val in summary.items():
            print(f"  {key}: {val}")
        return

    if not args.reset:
        parser.error("请使用 --reset 强制重置数据库，或 --verify-only 仅验证")

    print("正在清空并重建数据库…")
    reset_database()

    print("正在加载 Mock 数据…")
    result = seed_mock(with_clawhub=args.with_clawhub)

    print("\n=== Mock 数据加载完成 ===")
    for key, val in result["stats"].items():
        print(f"  {key}: {val}")
    print(f"  preferences: {result['preferences_path']}")

    actual = verify_summary()
    expected = result["patient_summary"]
    print("\n=== 队列统计 (patient_summary) ===")
    for key in ("waiting", "consulting", "completed", "first_visit", "followup"):
        ok = "✓" if actual[key] == expected[key] else "✗"
        print(f"  {key}: {actual[key]} (预期 {expected[key]}) {ok}")
    print(f"  total: {actual['total']}")

    print("\n提示: Agent 可通过 MCP patient_summary 或 GET /api/patients/summary 查询队列")


if __name__ == "__main__":
    main()
