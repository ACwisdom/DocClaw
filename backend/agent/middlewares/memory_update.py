"""自动记忆更新中间件（医疗版）。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from agent.config import USER_PREFERENCES_FILENAME

logger = logging.getLogger(__name__)

_TRIGGER_KEYWORDS = [
    "患者", "病历", "随访", "检查", "诊断", "处方", "复查", "提醒",
    "patient", "followup", "consult", "clinical",
]

_SKIP_PATTERNS = [
    "你好", "在吗", "hello", "hi", "你能做什么", "我的偏好",
]


def _is_meaningful_exchange(messages: List[BaseMessage]) -> Optional[str]:
    last_user = None
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            last_user = msg
            break
    if last_user is None:
        return None

    content = last_user.content
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    content = str(content).strip()
    if not content:
        return None

    lower = content.lower().replace(" ", "")
    if any(p.lower().replace(" ", "") in lower for p in _SKIP_PATTERNS):
        return None

    if any(kw.lower() in lower for kw in _TRIGGER_KEYWORDS):
        return content

    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "task":
                    return content
    return None


def _extract_ai_summary(messages: List[BaseMessage]) -> str:
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            content = msg.content
            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content)[:300]
    return ""


async def _extract_entities(
    model: BaseChatModel, user_message: str, ai_summary: str
) -> Dict[str, Any]:
    prompt = f"""从以下医疗对话中提取可记忆的信息。

User: {user_message}
Assistant summary: {ai_summary}

返回 JSON（仅 JSON，无其他文字）:
{{"recent_patients": ["患者名或slug"], "recent_topics": ["一句话主题"]}}"""

    try:
        response = await model.ainvoke(prompt)
        text = response.content
        if isinstance(text, list):
            text = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in text
            )
        text = str(text).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        logger.warning("MemoryUpdateMiddleware: LLM 提取失败", exc_info=True)
    return {"recent_patients": [], "recent_topics": []}


def _create_file_value(content_str: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "content": content_str.split("\n"),
        "created_at": now,
        "modified_at": now,
    }


class MemoryUpdateMiddleware(AgentMiddleware):
    """Agent 回复后自动更新医生偏好记忆。"""

    def __init__(self, model: BaseChatModel) -> None:
        super().__init__()
        self.model = model

    def after_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return None

    async def aafter_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        try:
            ctx = getattr(runtime, "context", None)
            if ctx is None:
                return None
            doctor_id = getattr(ctx, "doctor_id", None)
            if not doctor_id:
                return None

            messages: List[BaseMessage] = state.get("messages", [])
            user_message = _is_meaningful_exchange(messages)
            if user_message is None:
                return None

            ai_summary = _extract_ai_summary(messages)
            extracted = await _extract_entities(self.model, user_message, ai_summary)
            patients = extracted.get("recent_patients", [])
            topics = extracted.get("recent_topics", [])
            if not patients and not topics:
                return None

            store = getattr(runtime, "store", None)
            if store is None:
                return None

            namespace = (doctor_id,)
            key = USER_PREFERENCES_FILENAME
            try:
                item = await store.aget(namespace, key)
            except Exception:
                item = None

            lines: List[str] = []
            if item is not None and hasattr(item, "value"):
                value = item.value
                if isinstance(value, dict):
                    content = value.get("content", [])
                    lines = (
                        [str(line) for line in content]
                        if isinstance(content, list)
                        else str(content).split("\n")
                    )
                elif isinstance(value, str):
                    lines = value.split("\n")

            updated = _merge_preferences(lines, patients, topics)
            await store.aput(namespace, key, _create_file_value(updated))
        except Exception:
            logger.warning("MemoryUpdateMiddleware: 更新失败", exc_info=True)
        return None


def _merge_preferences(
    current_lines: List[str],
    new_patients: List[str],
    new_topics: List[str],
) -> str:
    existing_patients: List[str] = []
    existing_topics: List[str] = []
    clean = list(current_lines)

    for label, target in (
        ("recent_patients:", existing_patients),
        ("recent_topics:", existing_topics),
    ):
        for i, line in enumerate(clean):
            if line.strip().startswith(label):
                j = i + 1
                while j < len(clean) and clean[j].strip().startswith("- "):
                    target.append(clean[j].strip()[2:])
                    j += 1
                del clean[i:j]
                break

    merged_patients = list(new_patients)
    for p in existing_patients:
        if p not in merged_patients:
            merged_patients.append(p)
    merged_patients = merged_patients[:10]

    merged_topics = [t for t in new_topics if t]
    for t in existing_topics:
        if t not in merged_topics:
            merged_topics.append(t)
    merged_topics = merged_topics[:5]

    if clean and clean[-1].strip():
        clean.append("")
    clean.append("recent_patients:")
    for p in merged_patients:
        clean.append(f"  - {p}")
    clean.append("recent_topics:")
    for t in merged_topics:
        clean.append(f"  - {t}")

    return "\n".join(clean).strip() + "\n"
