import re
from typing import Literal

from pydantic import BaseModel

from ..models import Patient
from .schema import PENDING, OutpatientMedicalRecord

FIELD_LABELS = {
    "patient_name": "姓名",
    "gender": "性别",
    "age": "年龄",
    "chief_complaint": "主诉",
    "present_illness": "现病史",
    "past_history": "既往史",
    "allergy_history": "过敏史",
    "physical_exam": "查体",
    "auxiliary_exams": "辅助检查",
    "preliminary_diagnosis": "初步诊断",
    "treatment_plan": "处理意见",
}


class FieldDiff(BaseModel):
    field: str
    label: str
    generated: str
    source_value: str
    status: Literal["matched", "inferred", "missing", "conflict"]
    note: str = ""


def _is_pending(value: str) -> bool:
    return not value or value == PENDING


def _conversation_blob(conversation_text: str) -> str:
    return conversation_text or ""


def _has_evidence(text: str, conversation_text: str) -> bool:
    if not text or _is_pending(text):
        return False
    if text in conversation_text:
        return True
    tokens = [t for t in re.split(r"[，,；;\s]+", text) if len(t) >= 2]
    return any(token in conversation_text for token in tokens)


def _diff_patient_identity(
    field: str,
    generated: str,
    source_value: str,
) -> FieldDiff:
    label = FIELD_LABELS[field]
    if str(generated) == str(source_value):
        status: Literal["matched", "inferred", "missing", "conflict"] = "matched"
        note = ""
    else:
        status = "conflict"
        note = f"与患者档案不一致（档案：{source_value}）"
    return FieldDiff(
        field=field,
        label=label,
        generated=str(generated),
        source_value=str(source_value),
        status=status,
        note=note,
    )


def _diff_chief_complaint(
    generated: str,
    patient: Patient,
    conversation_text: str,
) -> FieldDiff:
    source = patient.chief_complaint or ""
    if _is_pending(generated):
        return FieldDiff(
            field="chief_complaint",
            label=FIELD_LABELS["chief_complaint"],
            generated=generated,
            source_value=source,
            status="missing",
            note="主诉待补充",
        )
    if source and (source in generated or generated in source):
        return FieldDiff(
            field="chief_complaint",
            label=FIELD_LABELS["chief_complaint"],
            generated=generated,
            source_value=source,
            status="matched",
        )
    if source and source not in conversation_text and generated != source:
        return FieldDiff(
            field="chief_complaint",
            label=FIELD_LABELS["chief_complaint"],
            generated=generated,
            source_value=source,
            status="conflict",
            note="与患者档案主诉不一致",
        )
    return FieldDiff(
        field="chief_complaint",
        label=FIELD_LABELS["chief_complaint"],
        generated=generated,
        source_value=source or conversation_text[:120],
        status="inferred",
        note="基于对话扩展归纳",
    )


def _diff_auxiliary_exams(
    generated: str,
    patient: Patient,
    conversation_text: str,
) -> FieldDiff:
    source = patient.completed_exams or ""
    context_blob = " ".join([source, patient.key_notes or "", conversation_text])
    if _is_pending(generated):
        return FieldDiff(
            field="auxiliary_exams",
            label=FIELD_LABELS["auxiliary_exams"],
            generated=generated,
            source_value=source or "无档案记录",
            status="missing",
        )
    if source and (source in generated or generated in source):
        return FieldDiff(
            field="auxiliary_exams",
            label=FIELD_LABELS["auxiliary_exams"],
            generated=generated,
            source_value=source,
            status="matched",
        )
    if _has_evidence(generated, conversation_text):
        return FieldDiff(
            field="auxiliary_exams",
            label=FIELD_LABELS["auxiliary_exams"],
            generated=generated,
            source_value=source or conversation_text[:120],
            status="inferred" if not source else "inferred",
            note="对话中出现但档案未记录" if not source else "对话补充检查信息",
        )
    if not _has_evidence(generated, context_blob):
        return FieldDiff(
            field="auxiliary_exams",
            label=FIELD_LABELS["auxiliary_exams"],
            generated=generated,
            source_value=source or "上下文无对应检查",
            status="conflict",
            note="辅助检查可能包含未在上下文中出现的项目",
        )
    return FieldDiff(
        field="auxiliary_exams",
        label=FIELD_LABELS["auxiliary_exams"],
        generated=generated,
        source_value=source or conversation_text[:120],
        status="inferred",
    )


def _diff_present_illness(generated: str, conversation_text: str) -> FieldDiff:
    if _is_pending(generated):
        return FieldDiff(
            field="present_illness",
            label=FIELD_LABELS["present_illness"],
            generated=generated,
            source_value=conversation_text[:160] or "对话中暂无现病史描述",
            status="missing",
        )
    if _has_evidence(generated, conversation_text):
        return FieldDiff(
            field="present_illness",
            label=FIELD_LABELS["present_illness"],
            generated=generated,
            source_value=conversation_text[:160],
            status="matched",
        )
    return FieldDiff(
        field="present_illness",
        label=FIELD_LABELS["present_illness"],
        generated=generated,
        source_value=conversation_text[:160] or "无直接对话摘录",
        status="inferred",
        note="模型归纳，建议核对",
    )


def _diff_generic_field(
    field: str,
    generated: str,
    conversation_text: str,
) -> FieldDiff:
    label = FIELD_LABELS[field]
    if _is_pending(generated):
        return FieldDiff(
            field=field,
            label=label,
            generated=generated,
            source_value=conversation_text[:120] or "对话暂无相关描述",
            status="missing",
        )
    if _has_evidence(generated, conversation_text):
        return FieldDiff(
            field=field,
            label=label,
            generated=generated,
            source_value=conversation_text[:120],
            status="matched",
        )
    return FieldDiff(
        field=field,
        label=label,
        generated=generated,
        source_value=conversation_text[:120] or "无直接证据",
        status="inferred",
        note="模型生成，建议核实",
    )


def compute_field_diffs(
    record: OutpatientMedicalRecord,
    patient: Patient,
    conversation_text: str,
) -> list[FieldDiff]:
    diffs: list[FieldDiff] = [
        _diff_patient_identity("patient_name", record.patient_name, patient.name),
        _diff_patient_identity("gender", record.gender, patient.gender),
        _diff_patient_identity("age", str(record.age), str(patient.age)),
        _diff_chief_complaint(record.chief_complaint, patient, conversation_text),
        _diff_present_illness(record.present_illness, conversation_text),
        _diff_auxiliary_exams(record.auxiliary_exams, patient, conversation_text),
    ]
    for field in (
        "past_history",
        "allergy_history",
        "physical_exam",
        "preliminary_diagnosis",
        "treatment_plan",
    ):
        diffs.append(
            _diff_generic_field(field, getattr(record, field), conversation_text)
        )
    return diffs


def warnings_from_diffs(diffs: list[FieldDiff]) -> list[str]:
    warnings: list[str] = []
    for diff in diffs:
        if diff.status == "conflict" and diff.note:
            warnings.append(diff.note)
        elif diff.status == "conflict":
            warnings.append(f"{diff.label}与上下文不一致，请核实")
    return warnings
