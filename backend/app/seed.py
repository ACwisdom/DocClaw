from sqlalchemy.orm import Session

from mock.loader import load_mock_data


def seed_database(db: Session, *, force: bool = False) -> None:
    """写入演示种子数据；默认仅在 doctors 表为空时执行。"""
    from .models import Doctor

    if not force and db.query(Doctor).first():
        return

    load_mock_data(db)
