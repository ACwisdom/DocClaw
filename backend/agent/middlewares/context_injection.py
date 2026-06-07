"""运行时医生上下文注入中间件。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

from agent.context_format import format_doctor_context_system_prompt

logger = logging.getLogger(__name__)


class ContextInjectionMiddleware(AgentMiddleware):
    """将 DoctorContext 注入对话开头。"""

    def before_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        ctx = getattr(runtime, "context", None)
        if ctx is None:
            logger.warning("ContextInjectionMiddleware: runtime.context 为 None")
            return None

        doctor_id = getattr(ctx, "doctor_id", None)
        if not doctor_id:
            logger.warning("ContextInjectionMiddleware: 缺少 doctor_id")
            return None

        from agent.schema import DoctorContext

        doctor_name = getattr(ctx, "doctor_name", None) or doctor_id
        department = getattr(ctx, "department", "") or "未指定科室"
        patient_slug = getattr(ctx, "patient_slug", None)

        doctor_ctx = DoctorContext(
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            department=department,
            patient_slug=patient_slug,
            patient_name=getattr(ctx, "patient_name", None),
            patient_gender=getattr(ctx, "patient_gender", None),
            patient_age=getattr(ctx, "patient_age", None),
            patient_chief_complaint=getattr(ctx, "patient_chief_complaint", None),
        )
        notice = format_doctor_context_system_prompt(doctor_ctx)
        return {"messages": [SystemMessage(content=notice)]}

    async def abefore_agent(
        self, state: Dict[str, Any], runtime: Any
    ) -> Optional[Dict[str, Any]]:
        return self.before_agent(state, runtime)
