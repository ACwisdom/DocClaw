"""Harness 环境变量加载。"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# 主模型（DeepSeek 优先，回退到 Skill Runtime 的 LLM_* 配置）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or os.getenv(
    "LLM_BASE_URL", "https://api.deepseek.com/v1"
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL") or os.getenv("LLM_MODEL", "deepseek-chat")

ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB", "doctorclaw_agent")
MONGODB_CHECKPOINT_COLLECTION = os.getenv(
    "MONGODB_CHECKPOINT_COLLECTION", "checkpoints"
)

# MCP / 业务 API
MEDICAL_API_BASE_URL = os.getenv(
    "MEDICAL_API_BASE_URL", "http://localhost:8000/api"
)
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
MCP_URL = os.getenv("MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}{MCP_PATH}")

# Agent API
AGENT_API_PORT = int(os.getenv("AGENT_API_PORT", "8090"))

# Sandbox（Phase 4 前可留空，使用本地 backend 降级）
SANDBOX_DOMAIN = os.getenv("SANDBOX_DOMAIN", "")
