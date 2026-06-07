import json

from dataclasses import dataclass, field



from sqlalchemy.orm import Session



from ..medical_record import (

    is_medical_record_intent,

    is_medical_record_skill,

    run_medical_record_skill,

)

from ..models import ConsultMessage, Patient, Skill

from .ai_service import get_active_skill

from .llm import ChatMessage, get_llm_provider





@dataclass

class SkillRunResult:

    content: str

    provider: str

    model: str | None

    skill_name: str

    used_fallback: bool = False

    message_type: str = "text"

    structured_data: dict | None = None

    metadata: str = ""

    validation_warnings: list[str] = field(default_factory=list)

    field_diffs: list[dict] = field(default_factory=list)

    raw_output: str = ""

def build_patient_context(patient: Patient) -> str:

    return f"""## 患者上下文

- 姓名：{patient.name}

- 性别/年龄：{patient.gender} · {patient.age}岁

- 就诊类型：{patient.visit_type.value}

- 主诉：{patient.chief_complaint}

- 已完成检查：{patient.completed_exams or "无"}

- 重点提示：{patient.key_notes or "无"}

- 初诊说明：{patient.first_visit_note or "无"}"""





def build_system_prompt(skill: Skill, patient: Patient) -> str:

    parts: list[str] = []

    if skill.system_prompt:

        parts.append(skill.system_prompt)

    if skill.input_desc:

        parts.append(f"\n## 输入说明\n{skill.input_desc}")

    if skill.output_desc:

        parts.append(f"\n## 输出说明\n{skill.output_desc}")

    parts.append(build_patient_context(patient))

    parts.append(

        "\n## 通用约束\n"

        "- 仅基于已提供的问诊信息与患者上下文作答，不得编造未出现的检查、用药或体征。\n"

        "- 信息不足时明确标注「待补充」，不要猜测。\n"

        "- 使用规范中文医学术语，回复简洁、可直接供医生审阅。"

    )

    return "\n".join(parts)





def map_history_to_messages(history: list[ConsultMessage]) -> list[ChatMessage]:

    messages: list[ChatMessage] = []

    for item in history:

        role = "user" if item.role == "doctor" else "assistant"

        messages.append(ChatMessage(role=role, content=item.content))

    return messages





def should_run_structured_medical_record(

    user_message: str,

    skill: Skill | None,

) -> bool:

    return is_medical_record_skill(skill) and is_medical_record_intent(user_message)





def run_skill(

    db: Session,

    patient: Patient,

    user_message: str,

    skill: Skill | None = None,

    history: list[ConsultMessage] | None = None,

) -> SkillRunResult:

    skill = skill or get_active_skill(db)

    skill_name = skill.name if skill else "智能病历助手"

    history = history or []



    if skill and should_run_structured_medical_record(user_message, skill):

        record_result = run_medical_record_skill(patient, user_message, skill, history)
        structured = record_result.record.model_dump_public()
        field_diffs_data = [d.model_dump() for d in record_result.field_diffs]
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
        return SkillRunResult(
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
        )



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

    response = provider.chat(llm_messages)



    return SkillRunResult(

        content=response.content,

        provider=response.provider,

        model=response.model,

        skill_name=skill_name,

        used_fallback=response.used_fallback,

    )


