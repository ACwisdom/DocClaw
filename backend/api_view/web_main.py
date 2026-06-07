"""
DocClaw Agent API — FastAPI 主应用 (:8090)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_view.agent_loader import agent_loader
from api_view.api.chat import router as agent_chat_router
from api_view.web_config import API_DESCRIPTION, API_TITLE, API_VERSION


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("正在启动 DocClaw Agent API...")
    print("=" * 50)
    try:
        await agent_loader.initialize()
    except Exception as exc:
        print(f"[WARN] Agent 初始化失败，健康检查仍可用: {exc}")
    print("=" * 50)
    print("DocClaw Agent API 启动完成")
    print("=" * 50)
    yield
    print("DocClaw Agent API 已关闭")


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_chat_router, prefix="/api")


@app.get("/", tags=["首页"])
async def root():
    return {
        "status": "ok",
        "name": API_TITLE,
        "version": API_VERSION,
        "description": API_DESCRIPTION,
        "docs": "/docs",
    }


def _chat_routes_registered() -> bool:
    return any(
        getattr(route, "path", None) == "/api/agent/chat"
        and "POST" in getattr(route, "methods", set())
        for route in app.routes
    )


@app.get("/health", tags=["系统"])
async def health_check():
    agent_ready = agent_loader._initialized and agent_loader._agent is not None
    routes_ready = _chat_routes_registered()
    ok = agent_ready and routes_ready
    return {
        "status": "healthy" if ok else "degraded",
        "service": API_TITLE,
        "version": API_VERSION,
        "agent_ready": agent_ready,
        "routes_ready": routes_ready,
        "agent_error": agent_loader.init_error,
        "hint": None
        if ok
        else (
            "Agent 对话路由未注册，请重启 start_agent.py（旧进程可能仍在占用 :8090）"
            if not routes_ready
            else "Agent 未初始化，请检查 DEEPSEEK_API_KEY 与上方日志"
        ),
    }
