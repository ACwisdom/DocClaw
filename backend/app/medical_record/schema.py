from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

REQUIRED_FIELDS = (
    "chief_complaint",
    "present_illness",
    "past_history",
    "allergy_history",
    "physical_exam",
    "auxiliary_exams",
    "preliminary_diagnosis",
    "treatment_plan",
)

PENDING = "待补充"


class OutpatientMedicalRecord(BaseModel):
    patient_name: str
    gender: str
    age: int
    chief_complaint: str
    present_illness: str
    past_history: str = PENDING
    allergy_history: str = PENDING
    physical_exam: str = PENDING
    auxiliary_exams: str = PENDING
    preliminary_diagnosis: str = PENDING
    treatment_plan: str = PENDING
    missing_fields: list[str] = Field(default_factory=list)
    confidence_notes: str = ""

    @field_validator(
        "past_history",
        "allergy_history",
        "physical_exam",
        "auxiliary_exams",
        "preliminary_diagnosis",
        "treatment_plan",
        mode="before",
    )
    @classmethod
    def empty_to_pending(cls, value: object) -> str:
        if value is None:
            return PENDING
        text = str(value).strip()
        return text or PENDING

    def collect_missing_fields(self) -> list[str]:
        labels = {
            "chief_complaint": "主诉",
            "present_illness": "现病史",
            "past_history": "既往史",
            "allergy_history": "过敏史",
            "physical_exam": "查体",
            "auxiliary_exams": "辅助检查",
            "preliminary_diagnosis": "初步诊断",
            "treatment_plan": "处理意见",
        }
        missing: list[str] = []
        for field, label in labels.items():
            value = getattr(self, field, "")
            if not value or value == PENDING:
                missing.append(label)
        return missing

    def to_markdown(self, skill_name: str, *, validated: bool = True) -> str:
        status = "已校验" if validated else "待校验"
        missing = self.missing_fields or self.collect_missing_fields()
        missing_line = f"- **缺项字段**：{', '.join(missing)}\n" if missing else ""
        notes = f"\n> **备注**：{self.confidence_notes}" if self.confidence_notes else ""

        return f"""好的，基于当前问诊信息，为您整理**门诊病历**（Structured Output · {status}）：

---

**门诊病历**

**姓名**：{self.patient_name}　**性别**：{self.gender}　**年龄**：{self.age}岁

**主诉**：{self.chief_complaint}

**现病史**：{self.present_illness}

**既往史**：{self.past_history}

**过敏史**：{self.allergy_history}

**查体**：{self.physical_exam}

**辅助检查**：{self.auxiliary_exams}

**初步诊断**：{self.preliminary_diagnosis}

**处理意见**：{self.treatment_plan}

---
{missing_line}> 由 **{skill_name}** 生成。请医生审核确认后使用。{notes}"""

    def model_dump_public(self) -> dict:
        data = self.model_dump()
        data["missing_fields"] = data.get("missing_fields") or self.collect_missing_fields()
        return data


class MedicalRecordResult(BaseModel):
    record: OutpatientMedicalRecord
    markdown: str
    raw_json: str
    validation_warnings: list[str] = Field(default_factory=list)
    field_diffs: list[Any] = Field(default_factory=list)
    provider: str = "mock"
    model: str | None = None
    used_fallback: bool = False
