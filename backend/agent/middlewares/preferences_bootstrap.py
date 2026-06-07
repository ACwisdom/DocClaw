"""医生偏好文件引导 — 确保 /memories/{doctor_id}/preferences.md 存在。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware

from agent.config import AGENT_DIR, USER_PREFERENCES_FILENAME

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = AGENT_DIR / "memory" / "preferences.template.md"


def _default_preferences_content() -> str:
    if _TEMPLATE_PATH.exists():
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        "# 医生工作偏好\n\nrecent_patients:\n\nrecent_topics:\n"
    )


def _create_file_value(content_str: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "content": content_str.split("\n"),
        "created_at": now,
        "modified_at": now,
    }


class PreferencesBootstrapMiddleware(AgentMiddleware):
    """首次对话前写入默认 preferences.md（若不存在）。"""

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        try:
            ctx = getattr(runtime, "context", None)
            store = getattr(runtime, "store", None)
            if ctx is None or store is None:
                return None

            doctor_id = getattr(ctx, "doctor_id", None)
            if not doctor_id:
                return None

            namespace = (doctor_id,)
            key = USER_PREFERENCES_FILENAME

            try:
                item = await store.aget(namespace, key)
            except Exception:
                item = None

            if item is not None:
                return None

            await store.aput(
                namespace,
                key,
                _create_file_value(_default_preferences_content()),
            )
            logger.info("已为医生 %s 初始化 preferences.md", doctor_id)
        except Exception:
            logger.warning("PreferencesBootstrapMiddleware: 初始化失败", exc_info=True)
        return None

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return None
