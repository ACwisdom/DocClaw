"""主 Agent 与子 Agent 中间件栈配置。"""

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from agent.config import SKILLS_STORE_NAMESPACE
from agent.middlewares.context_injection import ContextInjectionMiddleware
from agent.middlewares.memory_update import MemoryUpdateMiddleware
from agent.middlewares.preferences_bootstrap import PreferencesBootstrapMiddleware
from agent.middlewares.skills_sync import LocalSkillsSyncMiddleware, SkillsSyncMiddleware
from agent.middlewares.tools_summarization import build_summarization_middleware
from agent.middlewares.user_skills_restore import UserSkillsRestoreMiddleware


def create_clinical_middleware(model, backend) -> list:
    """clinical-assistant 子 Agent 中间件。"""
    return [
        build_summarization_middleware(backend, model),
        ModelCallLimitMiddleware(run_limit=50),
        ToolCallLimitMiddleware(run_limit=200),
    ]


def create_followup_middleware() -> list:
    """followup-executor 子 Agent 中间件。"""
    return [
        ModelCallLimitMiddleware(run_limit=20),
        ToolCallLimitMiddleware(run_limit=50),
    ]


def build_main_middleware(backend, summary_model, sandbox_backend=None) -> list:
    """构建与 AI+ERP 对齐的主 Agent 中间件栈。"""
    stack = [
        ContextInjectionMiddleware(),
        PreferencesBootstrapMiddleware(),
        build_summarization_middleware(backend, summary_model),
        MemoryUpdateMiddleware(model=summary_model),
        ModelCallLimitMiddleware(run_limit=50),
        ToolCallLimitMiddleware(run_limit=200),
    ]

    if sandbox_backend is not None:
        stack.insert(1, SkillsSyncMiddleware(sandbox_backend))
        stack.insert(
            2,
            UserSkillsRestoreMiddleware(sandbox_backend, SKILLS_STORE_NAMESPACE),
        )
    else:
        stack.insert(1, LocalSkillsSyncMiddleware())

    return stack
