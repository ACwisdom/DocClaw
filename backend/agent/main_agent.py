"""
主 Agent 入口模块 — DocClaw DeepAgents Harness。

Phase 0：11 阶段流水线骨架，可 create_deep_agent() 空跑。
Phase 1+：逐步接入 MCP 工具、子 Agent、中间件。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Optional

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain_core.runnables import RunnableConfig

from agent.backends.local_setup import setup_local_backend
from agent.config import (
    AGENTS_MD_FILENAME,
    BACKEND_DIR,
    CHECKPOINTER,
    LOCAL_AGENTS_MD,
    SANDBOX_CONFIG,
    SKILLS_STORE_NAMESPACE,
    STORE,
    SUMMARY_MODEL,
    MAIN_MODEL,
)
from agent.memory.prompts import system_prompt
from agent.schema import DoctorContext

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    level = logging.INFO if os.environ.get("APP_ENV") != "production" else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


_setup_logging()


async def create_main_agent(
    config: Optional[RunnableConfig] = None,
    *,
    sandbox_id: Optional[str] = None,
):
    """
    创建 DocClaw 医疗智能助理。

    11 阶段初始化流水线（Phase 0 骨架，部分阶段为占位日志）。
    """
    logger.info("=== 开始创建 DocClaw 医疗智能助理 ===")

    # ---- Phase 1: 沙箱 / 本地 Backend 配置 ----
    logger.info("Phase 1/11: 配置沙箱或本地 Backend...")
    use_sandbox = SANDBOX_CONFIG is not None
    backend = None
    sandbox_backend = None
    if use_sandbox:
        from agent.backends.sandbox_setup import setup_sandbox

        sandbox_backend = setup_sandbox(SANDBOX_CONFIG, sandbox_id=sandbox_id)
        logger.info("  使用 OpenSandbox 沙箱")
    else:
        logger.info("  SANDBOX_DOMAIN 未配置，使用本地 FilesystemBackend 降级")

    # ---- Phase 2: AGENTS.md 写入 ----
    logger.info("Phase 2/11: 写入 AGENTS.md...")
    if sandbox_backend and LOCAL_AGENTS_MD.exists():
        ag_content = LOCAL_AGENTS_MD.read_text(encoding="utf-8")
        sandbox_backend.upload_files([(AGENTS_MD_FILENAME, ag_content.encode("utf-8"))])
        logger.info("  AGENTS.md 已上传到沙箱")
    else:
        logger.info("  AGENTS.md 已通过 local_setup 同步到 workspace")

    # ---- Phase 3: CompositeBackend 分流 ----
    logger.info("Phase 3/11: 配置 CompositeBackend...")
    if use_sandbox and sandbox_backend:

        def backend(rt):
            return CompositeBackend(
                default=sandbox_backend,
                routes={
                    "/memories/": StoreBackend(
                        runtime=rt,
                        namespace=lambda rt: (
                            getattr(rt.context, "doctor_id", "doctor-li"),
                        ),
                    ),
                    "/persisted-skills/": StoreBackend(
                        runtime=rt,
                        namespace=lambda rt: SKILLS_STORE_NAMESPACE,
                    ),
                },
            )
    else:
        backend = setup_local_backend()

    # ---- Phase 4: MCP 工具加载（失败时降级 FastAPI 直连） ----
    logger.info("Phase 4/11: 加载医疗工具...")
    medical_tools = []
    medical_source = "none"
    try:
        from agent.tools.mcp_client import load_medical_tools_with_fallback

        medical_tools, medical_source = await load_medical_tools_with_fallback()
        logger.info(
            "  已加载 %d 个医疗工具 (来源: %s)",
            len(medical_tools),
            medical_source,
        )
    except ImportError:
        logger.info("  mcp_client 未实现，跳过医疗工具")
    except Exception as exc:
        logger.warning("  医疗工具加载失败: %s", exc)

    # ---- Phase 5: 通用工具合并 ----
    logger.info("Phase 5/11: 合并通用工具...")
    from agent.tools.hitl_tools import request_followup_confirm, request_record_confirm
    from agent.tools.medical_api_tools import MAIN_PATIENT_TOOL_NAMES, pick_tools_by_name
    from agent.tools.web_search import web_search

    available_tools = list(medical_tools) + [
        web_search,
        request_record_confirm,
        request_followup_confirm,
    ]
    main_tools = pick_tools_by_name(medical_tools, MAIN_PATIENT_TOOL_NAMES) + [
        web_search
    ]
    logger.info(
        "  工具池: %d 个；主 Agent 挂载: %s",
        len(available_tools),
        [getattr(t, "name", "?") for t in main_tools],
    )

    # ---- Phase 6: 子 Agent YAML 加载 ----
    logger.info("Phase 6/11: 加载子 Agent YAML...")
    subagents = []
    try:
        from agent.middleware_config import (
            create_clinical_middleware,
            create_followup_middleware,
        )
        from agent.subagents.loader import load_subagent_configs, resolve_subagent_tools

        raw_configs = load_subagent_configs()
        extra_middleware = {
            "clinical-assistant": create_clinical_middleware(SUMMARY_MODEL, backend),
            "followup-executor": create_followup_middleware(),
        }

        # ---- Phase 7: 子 Agent 中间件 ----
        logger.info("Phase 7/11: 子 Agent 中间件已配置")

        # ---- Phase 8: 子 Agent 工具名称解析 ----
        logger.info("Phase 8/11: 解析子 Agent 工具名称...")
        subagents = resolve_subagent_tools(
            raw_configs,
            available_tools,
            extra_middleware=extra_middleware,
        )
        logger.info("  已解析 %d 个子 Agent", len(subagents))
    except Exception as exc:
        logger.warning("  子 Agent 加载失败: %s", exc)

    # ---- Phase 9: 主 Agent 中间件栈 ----
    logger.info("Phase 9/11: 主 Agent 中间件栈...")
    main_middleware = []
    try:
        from agent.middleware_config import build_main_middleware

        main_middleware = build_main_middleware(backend, SUMMARY_MODEL, sandbox_backend)
        logger.info("  已加载 %d 个中间件", len(main_middleware))
    except Exception as exc:
        logger.warning("  中间件加载失败: %s", exc)

    # ---- Phase 10: create_deep_agent ----
    logger.info("Phase 10/11: 创建 Deep Agent...")
    agent_graph = create_deep_agent(
        model=MAIN_MODEL,
        system_prompt=system_prompt,
        skills=["/skills/main/"] if (BACKEND_DIR / "skills" / "main").exists() else [],
        memory=[AGENTS_MD_FILENAME],
        tools=main_tools,
        subagents=subagents or None,
        middleware=main_middleware,
        backend=backend,
        store=STORE,
        checkpointer=CHECKPOINTER,
        context_schema=DoctorContext,
    )

    logger.info("Phase 11/11: === DocClaw 医疗智能助理创建完成 ===")
    return agent_graph


async def _create_agent():
    return await create_main_agent()


class _AgentProxy:
    """懒加载 Agent 代理。"""

    def __init__(self):
        self._agent = None

    @property
    def _is_initialized(self):
        return self._agent is not None

    def _ensure_initialized(self):
        if self._agent is not None:
            return self._agent
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError(
                    "Agent 尚未初始化，请使用 await get_agent_async()"
                )
        except RuntimeError as e:
            if "Agent 尚未初始化" in str(e):
                raise
        self._agent = asyncio.run(_create_agent())
        return self._agent

    def __getattr__(self, name):
        return getattr(self._ensure_initialized(), name)


agent = _AgentProxy()


async def get_agent_async():
    global agent
    if isinstance(agent, _AgentProxy):
        if agent._is_initialized:
            return agent._agent
        agent._agent = await _create_agent()
        return agent._agent
    return agent


def get_agent():
    global agent
    if isinstance(agent, _AgentProxy):
        if agent._is_initialized:
            return agent._agent
        return agent._ensure_initialized()
    return agent
