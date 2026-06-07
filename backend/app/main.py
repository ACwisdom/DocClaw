from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine, migrate_schema
from .services.llm import get_llm_provider
from .routers import audit, consult, followup, his, medical_records, notifications, patients, skills, store
from .seed import seed_database
from .services.clawhub_importer import setup_clawhub_plaza
from .services.task_scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        seed_database(db)
        setup_clawhub_plaza(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="DocClaw 医疗 AI 工作台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(his.router)
app.include_router(skills.router)
app.include_router(store.router)
app.include_router(consult.router)
app.include_router(audit.router)
app.include_router(followup.router)
app.include_router(notifications.router)
app.include_router(medical_records.router)


@app.get("/api/health")
def health():
    settings = get_settings()
    provider = get_llm_provider()
    return {
        "status": "ok",
        "service": "DocClaw Medical AI Workbench",
        "llm": {
            "provider": settings.llm_provider,
            "active": provider.active_provider(),
            "model": settings.llm_model,
            "api_configured": bool(settings.llm_api_key.strip()),
            "fallback_enabled": settings.llm_fallback_to_mock,
        },
    }
