"""Harness 全局配置：模型、路径、MongoDB Checkpointer。"""

from datetime import timedelta
from pathlib import Path

import httpx
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.memory import InMemoryStore
from pymongo import MongoClient

from agent.env_utils import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MONGODB_CHECKPOINT_COLLECTION,
    MONGODB_DB_NAME,
    MONGODB_URI,
    SANDBOX_DOMAIN,
    ZHIPU_API_KEY,
    ZHIPU_BASE_URL,
)

# ---------- 模型配置 ----------
MAIN_MODEL = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    temperature=0.7,
    openai_api_key=DEEPSEEK_API_KEY,
    openai_api_base=DEEPSEEK_BASE_URL,
    max_tokens=8192,
)

SUMMARY_MODEL = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    temperature=0.3,
    openai_api_key=DEEPSEEK_API_KEY,
    openai_api_base=DEEPSEEK_BASE_URL,
    max_tokens=4096,
)

# ---------- 沙箱配置（Phase 0 可选） ----------
SANDBOX_CONFIG = None
if SANDBOX_DOMAIN:
    from opensandbox.config import ConnectionConfigSync

    SANDBOX_CONFIG = ConnectionConfigSync(
        domain=SANDBOX_DOMAIN,
        use_server_proxy=True,
        request_timeout=timedelta(seconds=60),
        transport=httpx.HTTPTransport(limits=httpx.Limits(max_connections=20)),
    )

# ---------- 路径常量 ----------
BACKEND_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = BACKEND_DIR / "agent"
LOCAL_SKILLS_DIR = BACKEND_DIR / "skills"
LOCAL_SUBAGENT_CONFIG_DIR = AGENT_DIR / "subagents" / "configs"
LOCAL_AGENTS_MD = AGENT_DIR / "memory" / "AGENTS.md"
LOCAL_WORKSPACE_DIR = BACKEND_DIR / "agent_workspace"
DOWNLOAD_DIR = BACKEND_DIR / "download"

SANDBOX_SKILLS_ROOT = "/skills"
SANDBOX_MEMORIES_ROOT = "/memories"
AGENTS_MD_FILENAME = "/AGENTS.md"
USER_PREFERENCES_FILENAME = "preferences.md"
PERSISTED_SKILLS_ROOT = "/persisted-skills"
SKILLS_STORE_NAMESPACE = ("skills",)

SCOPE_MAP = {
    "main": "main",
    "clinical-assistant": "clinical",
    "followup-executor": "followup",
}

# ---------- 持久化存储 ----------
STORE = InMemoryStore()

_mongodb_client: MongoClient | None = None
CHECKPOINTER = None

try:
    _mongodb_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
    _mongodb_client.admin.command("ping")
    CHECKPOINTER = MongoDBSaver(
        client=_mongodb_client,
        db_name=MONGODB_DB_NAME,
        checkpoint_collection_name=MONGODB_CHECKPOINT_COLLECTION,
    )
except Exception as exc:
    import logging

    logging.getLogger(__name__).warning(
        "MongoDB 不可用 (%s)，回退到 MemorySaver（HITL 续跑不可用）", exc
    )
    from langgraph.checkpoint.memory import MemorySaver

    CHECKPOINTER = MemorySaver()
