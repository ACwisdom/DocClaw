import json

from .schema import OutpatientMedicalRecord

MEDICAL_RECORD_INTENT_KEYWORDS = (
    "病历",
    "输出病历",
    "整理病历",
    "结构化",
    "门诊病历",
    "写病历",
    "生成病历",
    "帮我输出",
    "整理为",
)

JSON_SCHEMA_HINT = json.dumps(
    OutpatientMedicalRecord.model_json_schema(),
    ensure_ascii=False,
    indent=2,
)


def build_medical_record_system_prompt(
    skill_system_prompt: str,
    patient_context: str,
    conversation_summary: str,
) -> str:
    return f"""{skill_system_prompt}

你正在执行「门诊病历结构化」任务。必须仅依据患者上下文与问诊对话生成病历，不得编造。

## 输出要求
1. 只输出一个 JSON 对象，不要 Markdown，不要代码块，不要额外解释。
2. JSON 必须符合以下 Schema：
{JSON_SCHEMA_HINT}
3. 未在对话或患者上下文中出现的检查、用药、体征、诊断，对应字段填「待补充」。
4. missing_fields 列出仍为「待补充」的字段中文名。
5. confidence_notes 写明需医生重点核实的内容；无则留空字符串。

## 患者上下文
{patient_context}

## 问诊对话摘要
{conversation_summary}
"""
