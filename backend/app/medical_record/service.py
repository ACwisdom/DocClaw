import json
import re

from pydantic import ValidationError

from .diff import FieldDiff, compute_field_diffs, warnings_from_diffs

from ..models import ConsultMessage, Patient, Skill
from ..services.llm import ChatMessage, get_llm_provider
from .prompts import MEDICAL_RECORD_INTENT_KEYWORDS, build_medical_record_system_prompt
from .schema import PENDING, MedicalRecordResult, OutpatientMedicalRecord


def is_medical_record_skill(skill: Skill | None) -> bool:
    if not skill:
        return False
    if skill.id == "skill-record":
        return True
    if "病历" in skill.name:
        return True
    return skill.is_default and skill.task_type.value == "realtime"


def is_medical_record_intent(user_message: str) -> bool:
    text = user_message.strip()
    if not text:
        return False
    if any(keyword in text for keyword in MEDICAL_RECORD_INTENT_KEYWORDS):
        return True
    return text in {"输出", "整理", "生成"}


def summarize_conversation(history: list[ConsultMessage], user_message: str) -> str:
    lines: list[str] = []
    for item in history:
        if item.role == "system":
            continue
        speaker = "医生" if item.role == "doctor" else "助手"
        lines.append(f"{speaker}：{item.content}")
    lines.append(f"医生：{user_message}")
    return "\n".join(lines[-20:])


def extract_json_payload(raw: str) -> dict:
    text = raw.strip()
    if not text:
        raise ValueError("LLM 返回为空")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError("无法从模型输出中解析 JSON")


def apply_patient_identity(record: OutpatientMedicalRecord, patient: Patient) -> None:
    """结构化病历中的身份信息以患者档案为准。"""
    record.patient_name = patient.name
    record.gender = patient.gender
    record.age = patient.age


def normalize_structured_patient_identity(
    data: dict,
    patient: Patient,
) -> dict:
    """修正已存储/传输的结构化病历中的身份信息。"""
    normalized = dict(data)
    normalized["patient_name"] = patient.name
    normalized["gender"] = patient.gender
    normalized["age"] = patient.age
    return normalized


def post_validate_record(
    record: OutpatientMedicalRecord,
    patient: Patient,
    conversation_text: str,
) -> tuple[list[str], list[FieldDiff]]:
    diffs = compute_field_diffs(record, patient, conversation_text)
    warnings = warnings_from_diffs(diffs)
    record.missing_fields = record.collect_missing_fields()
    if warnings:
        note = "；".join(warnings)
        record.confidence_notes = (
            f"{record.confidence_notes}；{note}".strip("；")
            if record.confidence_notes
            else note
        )
    return warnings, diffs


def build_mock_record(patient: Patient, conversation_text: str) -> OutpatientMedicalRecord:
    present = patient.key_notes or f"患者自述{patient.chief_complaint}，详情待补充。"
    if conversation_text and conversation_text not in present:
        present = f"{present}（对话摘录：{conversation_text[-200:]}）"

    record = OutpatientMedicalRecord(
        patient_name=patient.name,
        gender=patient.gender,
        age=patient.age,
        chief_complaint=patient.chief_complaint,
        present_illness=present,
        past_history=PENDING,
        allergy_history=PENDING,
        physical_exam=PENDING,
        auxiliary_exams=patient.completed_exams or PENDING,
        preliminary_diagnosis=PENDING,
        treatment_plan=PENDING,
        confidence_notes="规则模拟模式生成，需医生审核。",
    )
    record.missing_fields = record.collect_missing_fields()
    return record


def run_medical_record_skill(
    patient: Patient,
    user_message: str,
    skill: Skill,
    history: list[ConsultMessage] | None = None,
) -> MedicalRecordResult:
    history = history or []
    patient_context = f"""- 姓名：{patient.name}
- 性别/年龄：{patient.gender} · {patient.age}岁
- 就诊类型：{patient.visit_type.value}
- 主诉：{patient.chief_complaint}
- 已完成检查：{patient.completed_exams or "无"}
- 重点提示：{patient.key_notes or "无"}
- 初诊说明：{patient.first_visit_note or "无"}"""
    conversation_summary = summarize_conversation(history, user_message)
    conversation_text = conversation_summary

    provider = get_llm_provider()
    use_mock = provider.active_provider() == "mock"

    if use_mock:
        record = build_mock_record(patient, conversation_text)
        warnings, field_diffs = post_validate_record(record, patient, conversation_text)
        apply_patient_identity(record, patient)
        raw_json = json.dumps(record.model_dump_public(), ensure_ascii=False, indent=2)
        return MedicalRecordResult(
            record=record,
            markdown=record.to_markdown(skill.name),
            raw_json=raw_json,
            validation_warnings=warnings,
            field_diffs=field_diffs,
            provider="mock",
            used_fallback=True,
        )

    system_prompt = build_medical_record_system_prompt(
        skill.system_prompt or "你是门诊病历助手。",
        patient_context,
        conversation_summary,
    )
    llm_messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(
            role="user",
            content=f"请根据以上信息生成门诊病历 JSON。医生当前请求：{user_message}",
        ),
    ]
    response = provider.chat(llm_messages, response_format={"type": "json_object"})

    try:
        payload = extract_json_payload(response.content)
        record = OutpatientMedicalRecord.model_validate(payload)
    except (ValueError, ValidationError) as exc:
        record = build_mock_record(patient, conversation_text)
        record.confidence_notes = f"JSON 解析/校验失败，已降级为模板草稿：{exc}"
        warnings, field_diffs = post_validate_record(record, patient, conversation_text)
        apply_patient_identity(record, patient)
        raw_json = json.dumps(record.model_dump_public(), ensure_ascii=False, indent=2)
        return MedicalRecordResult(
            record=record,
            markdown=record.to_markdown(skill.name, validated=False),
            raw_json=raw_json,
            validation_warnings=warnings,
            field_diffs=field_diffs,
            provider=response.provider,
            model=response.model,
            used_fallback=True,
        )

    warnings, field_diffs = post_validate_record(record, patient, conversation_text)
    apply_patient_identity(record, patient)
    raw_json = json.dumps(record.model_dump_public(), ensure_ascii=False, indent=2)
    return MedicalRecordResult(
        record=record,
        markdown=record.to_markdown(skill.name),
        raw_json=raw_json,
        validation_warnings=warnings,
        field_diffs=field_diffs,
        provider=response.provider,
        model=response.model,
        used_fallback=response.used_fallback,
    )
