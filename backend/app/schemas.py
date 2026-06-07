import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class DoctorOut(BaseModel):
    id: str
    name: str
    title: str
    department: str
    avatar: str

    model_config = {"from_attributes": True}


class PatientOut(BaseModel):
    id: str
    slug: str
    name: str
    gender: str
    age: int
    chief_complaint: str
    visit_type: str
    status: str
    priority: str
    queue_order: int
    completed_exams: str
    key_notes: str
    first_visit_note: str

    model_config = {"from_attributes": True}


class PatientSummary(BaseModel):
    waiting: int
    consulting: int
    completed: int
    first_visit: int
    followup: int


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    input_desc: str = ""
    output_desc: str = ""
    system_prompt: str = ""
    mode: str = ""
    tags: str = ""
    task_type: str = "realtime"
    icon: str = "description"


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    input_desc: Optional[str] = None
    output_desc: Optional[str] = None
    system_prompt: Optional[str] = None
    mode: Optional[str] = None
    tags: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None


class SkillOut(BaseModel):
    id: str
    doctor_id: str
    name: str
    description: str
    version: str
    mode: str
    input_desc: str
    output_desc: str
    system_prompt: str
    tags: str
    status: str
    task_type: str
    enabled: bool
    is_default: bool
    rating: float
    usage_count: int
    review_count: int
    icon: str
    created_at: datetime
    published_to_store: bool
    doctor_name: str = ""

    model_config = {"from_attributes": True}


class SkillStats(BaseModel):
    enabled: int
    draft: int
    published: int
    default: int


class StoreSkillOut(BaseModel):
    id: str
    name: str
    author: str
    description: str
    category: str
    version: str
    tags: str
    install_count: int
    rating: float
    scenarios: str
    compatibility: str
    highlights: str
    publisher: str
    updated_at: str
    is_featured: bool
    is_editors_choice: bool
    clawhub_slug: str | None = None
    source: str = "local"

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str
    role: str = "doctor"


class MessageOut(BaseModel):
    id: str
    patient_id: str
    role: str
    content: str
    message_type: str
    meta_json: str = ""
    structured_data: Optional[dict[str, Any]] = None
    validation_warnings: list[str] = Field(default_factory=list)
    field_diffs: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def parse_metadata(self) -> "MessageOut":
        if not self.meta_json:
            return self
        try:
            payload = json.loads(self.meta_json)
        except json.JSONDecodeError:
            return self
        if isinstance(payload.get("structured_data"), dict):
            self.structured_data = payload["structured_data"]
        if isinstance(payload.get("validation_warnings"), list):
            self.validation_warnings = payload["validation_warnings"]
        if isinstance(payload.get("field_diffs"), list):
            self.field_diffs = payload["field_diffs"]
        return self


class ChatRequest(BaseModel):
    content: str
    skill_id: Optional[str] = None


class FollowUpPlanCreate(BaseModel):
    patient_id: str
    title: str
    description: str = ""
    skill_id: Optional[str] = None
    tasks: list["FollowUpTaskCreate"] = []


class FollowUpTaskCreate(BaseModel):
    title: str
    description: str = ""
    scheduled_at: datetime


class FollowUpTaskOut(BaseModel):
    id: str
    plan_id: str
    title: str
    description: str
    scheduled_at: datetime
    status: str
    result: str
    executed_at: Optional[datetime] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    plan_title: Optional[str] = None

    model_config = {"from_attributes": True}


class FollowUpPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class FollowUpTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None


class FollowUpPlanOut(BaseModel):
    id: str
    patient_id: str
    doctor_id: str
    title: str
    description: str
    skill_id: Optional[str] = None
    status: str
    created_at: datetime
    tasks: list[FollowUpTaskOut] = []

    model_config = {"from_attributes": True}


class NotificationOut(BaseModel):
    id: str
    title: str
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    title: str
    content: str
    doctor_id: Optional[str] = None


class AgentMessageCreate(BaseModel):
    content: str
    role: str = "assistant"


class MedicalRecordConfirm(BaseModel):
    content: str
    structured_data: Optional[dict[str, Any]] = None
