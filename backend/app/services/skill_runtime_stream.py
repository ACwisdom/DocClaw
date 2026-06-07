import json
from collections.abc import Iterator
from dataclasses import dataclass

from ..medical_record import run_medical_record_skill
from ..models import ConsultMessage, Patient, Skill
from .llm import ChatMessage, get_llm_provider
from .skill_runtime import (
    SkillRunResult,
    build_patient_context,
    build_system_prompt,
    map_history_to_messages,
    should_run_structured_medical_record,
)


@dataclass
class StreamSkillOutcome:
    result: SkillRunResult
    provider: str
    model: str | None
    used_fallback: bool = False


def format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def iter_skill_stream_events(
    patient: Patient,
    user_message: str,
    skill: Skill | None = None,
    history: list[ConsultMessage] | None = None,
) -> Iterator[str | StreamSkillOutcome]:
    skill = skill or None
    skill_name = skill.name if skill else "智能病历助手"
    history = history or []

    if skill and should_run_structured_medical_record(user_message, skill):
        yield format_sse_event("status", {"text": "正在生成结构化病历..."})
        record_result = run_medical_record_skill(patient, user_message, skill, history)
        structured = record_result.record.model_dump_public()
        field_diffs_data = [d.model_dump() for d in record_result.field_diffs]
        yield format_sse_event(
            "structured",
            {
                "structured_data": structured,
                "validation_warnings": record_result.validation_warnings,
                "field_diffs": field_diffs_data,
            },
        )
        metadata = json.dumps(
            {
                "type": "outpatient_medical_record",
                "schema_version": "1.0",
                "structured_data": structured,
                "validation_warnings": record_result.validation_warnings,
                "field_diffs": field_diffs_data,
                "raw_json": record_result.raw_json,
            },
            ensure_ascii=False,
        )
        outcome = StreamSkillOutcome(
            result=SkillRunResult(
                content=record_result.markdown,
                provider=record_result.provider,
                model=record_result.model,
                skill_name=skill_name,
                used_fallback=record_result.used_fallback,
                message_type="medical_record",
                structured_data=structured,
                metadata=metadata,
                validation_warnings=record_result.validation_warnings,
                field_diffs=field_diffs_data,
                raw_output=record_result.raw_json,
            ),
            provider=record_result.provider,
            model=record_result.model,
            used_fallback=record_result.used_fallback,
        )
        yield outcome
        return

    if skill:
        system_content = build_system_prompt(skill, patient)
    else:
        system_content = (
            "你是医疗 AI 助手，协助医生完成门诊问诊与病历整理。"
            f"\n\n{build_patient_context(patient)}"
        )

    llm_messages = [ChatMessage(role="system", content=system_content)]
    if history:
        llm_messages.extend(map_history_to_messages(history))
    llm_messages.append(ChatMessage(role="user", content=user_message))

    provider = get_llm_provider()
    content_parts: list[str] = []
    used_fallback = provider.active_provider() == "mock"

    try:
        for delta in provider.chat_stream(llm_messages):
            content_parts.append(delta)
            yield format_sse_event("chunk", {"delta": delta})
    except Exception as exc:
        yield format_sse_event("error", {"message": str(exc), "fallback": True})
        raise

    content = "".join(content_parts).strip()
    if not content:
        raise RuntimeError("LLM 流式返回内容为空")

    outcome = StreamSkillOutcome(
        result=SkillRunResult(
            content=content,
            provider=provider.active_provider(),
            model=None,
            skill_name=skill_name,
            used_fallback=used_fallback,
            raw_output=content,
        ),
        provider=provider.active_provider(),
        model=None,
        used_fallback=used_fallback,
    )
    yield outcome
