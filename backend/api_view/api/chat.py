"""
Agent 对话 API — SSE 流式对话与 HITL 恢复。

端点:
  POST /api/agent/chat   — 流式对话
  POST /api/agent/resume — HITL 续跑
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from agent.context_format import format_doctor_context_display, strip_system_context_from_response
from agent.queue_data import (
    fetch_patient_summary,
    format_queue_summary_reply,
    is_queue_summary_query,
)
from agent.schema import ChatRequest, DoctorContext, ResumeRequest
from api_view.agent_loader import agent_loader
from api_view.audit_client import report_tool_call_finish, report_tool_call_start

router = APIRouter(prefix="/agent", tags=["Agent"])


def create_sse_message(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def extract_subagent_name(namespace: tuple) -> str:
    for segment in namespace:
        if segment.startswith("tools:"):
            return segment.replace("tools:", "")
    return "main"


def extract_content_from_token(token) -> str:
    if not hasattr(token, "content"):
        return ""
    content = token.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content) if content is not None else ""


def serialize_tool_result(content) -> dict:
    result = {"text": "", "images": []}
    if isinstance(content, str):
        result["text"] = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        result["text"] = "".join(parts)
    else:
        result["text"] = str(content) if content is not None else ""
    return result


def build_doctor_context(request: ChatRequest) -> DoctorContext:
    ctx = DoctorContext(
        doctor_id=request.doctor_id or "doctor-li",
        doctor_name=request.doctor_name or "李医生",
        department=request.department or "呼吸内科门诊",
        patient_slug=request.patient_slug,
        patient_name=request.patient_name,
        patient_gender=request.patient_gender,
        patient_age=request.patient_age,
        patient_chief_complaint=request.patient_chief_complaint,
    )
    return enrich_doctor_context_from_db(ctx)


def enrich_doctor_context_from_db(ctx: DoctorContext) -> DoctorContext:
    """若仅有 slug，从数据库补全当前患者档案（与问诊页绑定一致）。"""
    if not ctx.patient_slug or ctx.patient_name:
        return ctx
    try:
        from app.database import SessionLocal
        from app.models import Patient

        db = SessionLocal()
        try:
            patient = db.query(Patient).filter(Patient.slug == ctx.patient_slug).first()
            if not patient:
                return ctx
            return DoctorContext(
                doctor_id=ctx.doctor_id,
                doctor_name=ctx.doctor_name,
                department=ctx.department,
                patient_slug=ctx.patient_slug,
                patient_name=patient.name,
                patient_gender=patient.gender,
                patient_age=patient.age,
                patient_chief_complaint=patient.chief_complaint,
            )
        finally:
            db.close()
    except Exception:
        return ctx


def build_doctor_context_from_payload(payload: dict | None) -> DoctorContext:
    data = payload or {}
    ctx = DoctorContext(
        doctor_id=data.get("doctor_id", "doctor-li"),
        doctor_name=data.get("doctor_name", "李医生"),
        department=data.get("department", "呼吸内科门诊"),
        patient_slug=data.get("patient_slug"),
        patient_name=data.get("patient_name"),
        patient_gender=data.get("patient_gender"),
        patient_age=data.get("patient_age"),
        patient_chief_complaint=data.get("patient_chief_complaint"),
    )
    return enrich_doctor_context_from_db(ctx)


def build_resume_data(request: ResumeRequest) -> dict:
    """将 DocClaw ResumeRequest 转为 LangGraph Command.resume 格式。"""
    action = request.action.lower()
    payload = dict(request.payload or {})

    if action in ("approve", "reject") and not payload:
        return {"decisions": [{"type": action}]}

    if action == "approve":
        return {**payload, "action": "approve", "approved": True}
    if action == "reject":
        return {**payload, "action": "reject", "approved": False}
    if action == "edit":
        return {**payload, "action": "edit"}

    raise HTTPException(400, f"不支持的 action: {request.action}")


async def stream_chat_response(
    *,
    message: Optional[str] = None,
    thread_id: str,
    context: Optional[DoctorContext] = None,
    resume_data: Optional[dict] = None,
) -> AsyncIterator[str]:
    """流式生成对话响应，支持 HITL interrupt/resume。"""
    config = agent_loader.create_config(
        thread_id=thread_id,
        doctor_id=context.doctor_id if context else "doctor-li",
    )
    collected_content = ""
    tool_call_stack: list[dict] = []
    doctor_id = context.doctor_id if context else "doctor-li"
    patient_slug = context.patient_slug if context else None

    if resume_data is not None:
        existing = await agent_loader.get_display_messages(thread_id) or []
        display_messages = existing
        current_input = Command(resume=resume_data)
    else:
        current_input = {"messages": [{"role": "user", "content": message}]}
        display_messages = [
            {"id": f"user-{uuid.uuid4()}", "role": "user", "content": message}
        ]

    def _last_is_assistant() -> bool:
        return bool(display_messages and display_messages[-1]["role"] == "assistant")

    try:
        if context is not None and resume_data is None:
            yield create_sse_message(
                {
                    "type": "trace_step",
                    "kind": "context",
                    "content": "系统上下文",
                    "detail": format_doctor_context_display(context),
                    "source": "main",
                }
            )

        # 演示快捷路径：待接诊统计直接返回队列数据（API 或 mock），避免 LLM 误报「未接入 HIS」
        if message and resume_data is None and is_queue_summary_query(message):
            summary = await fetch_patient_summary()
            tool_id = str(uuid.uuid4())
            doctor_name = (context.doctor_name if context else None) or "医生"
            answer = format_queue_summary_reply(summary, doctor_name=doctor_name)
            summary_text = json.dumps(summary, ensure_ascii=False)

            yield create_sse_message(
                {
                    "type": "tool_call",
                    "tool_call_id": tool_id,
                    "tool_name": "his_queue_summary",
                    "source": "main",
                }
            )
            yield create_sse_message(
                {
                    "type": "tool_result",
                    "tool_name": "his_queue_summary",
                    "tool_call_id": tool_id,
                    "text": summary_text,
                    "source": "main",
                }
            )
            yield create_sse_message(
                {"type": "token", "content": answer, "source": "main"}
            )

            display_messages.append(
                {
                    "id": f"assistant-{uuid.uuid4()}",
                    "role": "assistant",
                    "content": answer,
                    "source": "main",
                }
            )
            existing = await agent_loader.get_display_messages(thread_id) or []
            await agent_loader.save_display_messages(
                thread_id, existing + display_messages
            )
            yield create_sse_message(
                {
                    "type": "done",
                    "thread_id": thread_id,
                    "content": answer,
                }
            )
            return

        async for chunk in agent_loader.agent.astream(
            input=current_input,
            config=config,
            context=context,
            stream_mode=["messages", "values"],
            subgraphs=True,
            version="v2",
        ):
            chunk_type = chunk.get("type")

            if chunk_type == "values" and chunk.get("interrupts"):
                for interrupt in chunk["interrupts"]:
                    interrupt_value = interrupt.value
                    if "action_requests" in interrupt_value:
                        yield create_sse_message(
                            {
                                "type": "interrupt",
                                "interrupt_type": "hitl_approval",
                                "action_requests": interrupt_value["action_requests"],
                                "review_configs": interrupt_value.get(
                                    "review_configs", []
                                ),
                                "thread_id": thread_id,
                            }
                        )
                    elif interrupt_value.get("type") == "medical_record_confirm":
                        yield create_sse_message(
                            {
                                "type": "interrupt",
                                "interrupt_type": "medical_record_confirm",
                                "patient_slug": interrupt_value.get("patient_slug"),
                                "draft_content": interrupt_value.get("draft_content"),
                                "structured_data": interrupt_value.get(
                                    "structured_data", {}
                                ),
                                "thread_id": thread_id,
                            }
                        )
                    elif interrupt_value.get("type") == "followup_plan_confirm":
                        yield create_sse_message(
                            {
                                "type": "interrupt",
                                "interrupt_type": "followup_plan_confirm",
                                "patient_id": interrupt_value.get("patient_id"),
                                "title": interrupt_value.get("title"),
                                "description": interrupt_value.get("description"),
                                "tasks": interrupt_value.get("tasks", []),
                                "thread_id": thread_id,
                            }
                        )
                    else:
                        yield create_sse_message(
                            {
                                "type": "interrupt",
                                "interrupt_type": interrupt_value.get(
                                    "type", "unknown"
                                ),
                                "interrupt_value": interrupt_value,
                                "thread_id": thread_id,
                            }
                        )

                await agent_loader.save_display_messages(thread_id, display_messages)
                yield create_sse_message(
                    {
                        "type": "done",
                        "thread_id": thread_id,
                        "content": collected_content,
                        "interrupted": True,
                    }
                )
                return

            if chunk_type != "messages":
                continue

            token, _metadata = chunk["data"]
            namespace = chunk.get("ns", ())
            is_subagent = any(s.startswith("tools:") for s in namespace)
            source = extract_subagent_name(namespace) if is_subagent else "main"

            if hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
                for tool_chunk in token.tool_call_chunks:
                    if tool_chunk.get("name"):
                        tool_id = str(uuid.uuid4())
                        tool_call_stack.append(
                            {
                                "id": tool_id,
                                "name": tool_chunk["name"],
                                "args": "",
                                "source": source,
                            }
                        )
                        event = {
                            "type": "tool_call",
                            "tool_call_id": tool_id,
                            "tool_name": tool_chunk["name"],
                            "source": source,
                        }
                        yield create_sse_message(event)

                        if tool_chunk["name"] == "task":
                            yield create_sse_message(
                                {
                                    "type": "subagent",
                                    "tool_call_id": tool_id,
                                    "source": source,
                                }
                            )

                        display_messages.append(
                            {
                                "id": tool_id,
                                "role": "tool",
                                "tool_name": tool_chunk["name"],
                                "args": "",
                                "text": "",
                                "source": source,
                                "tool_status": "calling",
                            }
                        )
                        try:
                            await report_tool_call_start(
                                doctor_id=doctor_id,
                                thread_id=thread_id,
                                tool_name=tool_chunk["name"],
                                tool_call_id=tool_id,
                                source=source,
                                patient_slug=patient_slug,
                            )
                        except Exception:
                            pass

                    if tool_chunk.get("args"):
                        args_str = tool_chunk["args"]
                        if tool_call_stack:
                            tool_call_stack[-1]["args"] += args_str
                        for dm in reversed(display_messages):
                            if (
                                dm["role"] == "tool"
                                and dm["tool_status"] == "calling"
                            ):
                                dm["args"] += args_str
                                break

            if hasattr(token, "type") and token.type == "tool":
                tool_name = getattr(token, "name", "unknown")
                serialized = serialize_tool_result(getattr(token, "content", ""))
                finished = tool_call_stack.pop() if tool_call_stack else None
                tool_id = finished["id"] if finished else ""

                yield create_sse_message(
                    {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "tool_call_id": tool_id,
                        "text": serialized["text"],
                        "source": source,
                    }
                )

                for dm in reversed(display_messages):
                    if dm["role"] == "tool" and dm["id"] == tool_id:
                        dm["text"] = serialized["text"]
                        dm["tool_status"] = "done"
                        break

                try:
                    await report_tool_call_finish(
                        doctor_id=doctor_id,
                        thread_id=thread_id,
                        tool_name=tool_name,
                        tool_call_id=tool_id,
                        result_text=serialized["text"],
                        source=source,
                        patient_slug=patient_slug,
                    )
                except Exception:
                    pass

            content_text = extract_content_from_token(token)
            has_tool_calls = (
                hasattr(token, "tool_call_chunks") and token.tool_call_chunks
            )
            is_tool_result = hasattr(token, "type") and token.type == "tool"

            if content_text and not has_tool_calls and not is_tool_result:
                prev_visible = strip_system_context_from_response(collected_content)
                collected_content += content_text
                visible = strip_system_context_from_response(collected_content)
                token_visible = visible[len(prev_visible) :]
                if token_visible:
                    yield create_sse_message(
                        {"type": "token", "content": token_visible, "source": source}
                    )
                if _last_is_assistant():
                    display_messages[-1]["content"] = visible
                    display_messages[-1]["source"] = source
                else:
                    display_messages.append(
                        {
                            "id": f"assistant-{uuid.uuid4()}",
                            "role": "assistant",
                            "content": visible,
                            "source": source,
                        }
                    )

        for dm in display_messages:
            if dm["role"] == "tool" and dm.get("tool_status") == "calling":
                dm["tool_status"] = "done"

        display_messages = [
            dm
            for dm in display_messages
            if not (dm["role"] == "assistant" and not dm.get("content"))
        ]

        if resume_data is None:
            existing = await agent_loader.get_display_messages(thread_id) or []
            all_messages = existing + display_messages
        else:
            all_messages = display_messages
        await agent_loader.save_display_messages(thread_id, all_messages)

        yield create_sse_message(
            {
                "type": "done",
                "thread_id": thread_id,
                "content": strip_system_context_from_response(collected_content),
            }
        )

    except Exception as exc:
        yield create_sse_message({"type": "error", "message": str(exc)})


@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """Agent 流式对话（SSE）。"""
    if not agent_loader._initialized or agent_loader._agent is None:
        raise HTTPException(503, "Agent 未就绪", headers={"X-Agent-Error": agent_loader.init_error or ""})

    thread_id = request.thread_id or str(uuid.uuid4())
    context = build_doctor_context(request)

    return StreamingResponse(
        stream_chat_response(
            message=request.message,
            thread_id=thread_id,
            context=context,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Thread-Id": thread_id,
        },
    )


@router.post("/resume")
async def agent_resume(request: ResumeRequest):
    """HITL 中断恢复（SSE 续流）。"""
    if not agent_loader._initialized or agent_loader._agent is None:
        raise HTTPException(503, "Agent 未就绪")

    resume_data = build_resume_data(request)
    context = build_doctor_context_from_payload(request.payload)

    return StreamingResponse(
        stream_chat_response(
            thread_id=request.thread_id,
            context=context,
            resume_data=resume_data,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
