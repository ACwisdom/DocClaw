import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class VisitStatus(str, enum.Enum):
    WAITING = "waiting"
    CONSULTING = "consulting"
    COMPLETED = "completed"


class VisitType(str, enum.Enum):
    FIRST = "first"
    FOLLOWUP = "followup"


class Priority(str, enum.Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    CHRONIC = "chronic"


class SkillStatus(str, enum.Enum):
    DRAFT = "draft"
    ENABLED = "enabled"
    PUBLISHED = "published"
    DEFAULT = "default"


class TaskType(str, enum.Enum):
    REALTIME = "realtime"
    SCHEDULED = "scheduled"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    avatar: Mapped[str] = mapped_column(String(10), default="李")

    skills: Mapped[list["Skill"]] = relationship(back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    gender: Mapped[str] = mapped_column(String(10))
    age: Mapped[int] = mapped_column(Integer)
    chief_complaint: Mapped[str] = mapped_column(Text)
    visit_type: Mapped[VisitType] = mapped_column(Enum(VisitType))
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus))
    priority: Mapped[Priority] = mapped_column(Enum(Priority))
    queue_order: Mapped[int] = mapped_column(Integer, default=0)
    completed_exams: Mapped[str] = mapped_column(Text, default="")
    key_notes: Mapped[str] = mapped_column(Text, default="")
    first_visit_note: Mapped[str] = mapped_column(Text, default="")

    messages: Mapped[list["ConsultMessage"]] = relationship(back_populates="patient")
    followup_plans: Mapped[list["FollowUpPlan"]] = relationship(back_populates="patient")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), default="v1.0")
    mode: Mapped[str] = mapped_column(String(200), default="")
    input_desc: Mapped[str] = mapped_column(Text, default="")
    output_desc: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[SkillStatus] = mapped_column(Enum(SkillStatus), default=SkillStatus.DRAFT)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), default=TaskType.REALTIME)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str] = mapped_column(String(50), default="description")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_to_store: Mapped[bool] = mapped_column(Boolean, default=False)
    store_skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    doctor: Mapped["Doctor"] = relationship(back_populates="skills")


class StoreSkill(Base):
    __tablename__ = "store_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="clinical")
    version: Mapped[str] = mapped_column(String(20), default="v1.0")
    tags: Mapped[str] = mapped_column(String(500), default="")
    install_count: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=4.5)
    scenarios: Mapped[str] = mapped_column(Text, default="")
    compatibility: Mapped[str] = mapped_column(Text, default="")
    highlights: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[str] = mapped_column(String(20), default="")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_editors_choice: Mapped[bool] = mapped_column(Boolean, default=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    input_desc: Mapped[str] = mapped_column(Text, default="")
    output_desc: Mapped[str] = mapped_column(Text, default="")
    clawhub_slug: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    source: Mapped[str] = mapped_column(String(30), default="local")


class ConsultMessage(Base):
    __tablename__ = "consult_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(30), default="text")
    meta_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="messages")


class AgentToolExecutionLog(Base):
    """Agent Harness 工具调用链审计（Phase 4）。"""

    __tablename__ = "agent_tool_execution_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(120))
    tool_call_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    source: Mapped[str] = mapped_column(String(60), default="main")
    args_snapshot: Mapped[str] = mapped_column(Text, default="")
    result_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="calling")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SkillExecutionLog(Base):
    __tablename__ = "skill_execution_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consult_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_type: Mapped[str] = mapped_column(String(20), default="realtime")
    user_input: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="success")
    input_snapshot: Mapped[str] = mapped_column(Text, default="")
    raw_output: Mapped[str] = mapped_column(Text, default="")
    structured_output: Mapped[str] = mapped_column(Text, default="")
    validation_warnings: Mapped[str] = mapped_column(Text, default="")
    field_diffs: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FollowUpPlan(Base):
    __tablename__ = "followup_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    patient: Mapped["Patient"] = relationship(back_populates="followup_plans")
    tasks: Mapped[list["FollowUpTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class FollowUpTask(Base):
    __tablename__ = "followup_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("followup_plans.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    result: Mapped[str] = mapped_column(Text, default="")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plan: Mapped["FollowUpPlan"] = relationship(back_populates="tasks")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_id)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
