from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./docclaw.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema() -> None:
    inspector = inspect(engine)
    if "consult_messages" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("consult_messages")}
        if "meta_json" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE consult_messages ADD COLUMN meta_json TEXT NOT NULL DEFAULT ''")
                )

    if "skill_execution_logs" not in inspector.get_table_names():
        from .models import SkillExecutionLog

        SkillExecutionLog.__table__.create(bind=engine)

    if "agent_tool_execution_logs" not in inspector.get_table_names():
        from .models import AgentToolExecutionLog

        AgentToolExecutionLog.__table__.create(bind=engine)

    if "store_skills" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("store_skills")}
        with engine.begin() as conn:
            if "clawhub_slug" not in columns:
                conn.execute(text("ALTER TABLE store_skills ADD COLUMN clawhub_slug VARCHAR(120)"))
            if "source" not in columns:
                conn.execute(text("ALTER TABLE store_skills ADD COLUMN source VARCHAR(30) NOT NULL DEFAULT 'local'"))
        indexes = {idx["name"] for idx in inspector.get_indexes("store_skills")}
        if "uq_store_skills_clawhub_slug" not in indexes:
            with SessionLocal() as db:
                from .services.clawhub_importer import dedupe_clawhub_store_skills

                dedupe_clawhub_store_skills(db)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_store_skills_clawhub_slug "
                        "ON store_skills(clawhub_slug) WHERE clawhub_slug IS NOT NULL"
                    )
                )
