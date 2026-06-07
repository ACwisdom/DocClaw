"""
Harness 数据结构定义。

DoctorContext 对标 AI+ERP 的 ProcurementContext，在 invoke 时注入医生身份。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class DoctorContext:
    """运行时上下文，由调用方在 invoke 时传入。"""

    doctor_id: str
    doctor_name: str
    department: str
    patient_slug: Optional[str] = None
    patient_name: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_age: Optional[int] = None
    patient_chief_complaint: Optional[str] = None


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(..., description="用户消息")
    thread_id: Optional[str] = Field(None, description="会话 ID")
    patient_slug: Optional[str] = Field(None, description="当前患者 slug")
    patient_name: Optional[str] = Field(None, description="当前患者姓名")
    patient_gender: Optional[str] = Field(None, description="当前患者性别")
    patient_age: Optional[int] = Field(None, description="当前患者年龄")
    patient_chief_complaint: Optional[str] = Field(None, description="当前患者主诉")
    doctor_id: Optional[str] = Field("doctor-li", description="医生 ID")
    doctor_name: Optional[str] = Field("李医生", description="医生姓名")
    department: Optional[str] = Field("呼吸内科门诊", description="科室")


class ResumeRequest(BaseModel):
    """HITL 恢复请求（Phase 2 启用）。"""

    thread_id: str
    action: str = Field(..., description="approve / reject / edit")
    payload: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    """消息模型。"""

    id: str
    role: str
    content: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    source: Optional[str] = None


class StreamTokenEvent(BaseModel):
    type: str = "token"
    content: str
    source: str = "main"


class StreamDoneEvent(BaseModel):
    type: str = "done"
    thread_id: str
    content: str = ""


class StreamErrorEvent(BaseModel):
    type: str = "error"
    message: str
