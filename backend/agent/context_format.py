"""医生运行时上下文格式化（注入 Agent 与前端调试 trace 共用）。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.schema import DoctorContext

CONTEXT_END_MARKER = "请先 read_file 读取偏好文件（若存在）。"
CONTEXT_START_MARKER = "【系统上下文】"
INTERNAL_NOTICE_MARKER = "【重要】以上内容为内部会话上下文"
INTERNAL_NOTICE_END = "直接回答医生的问题即可。"
PATIENT_INFO_HEADER = "的信息如下"
RECENT_PREFS_JSON_FENCE_RE = re.compile(
    r"```json\s*\n?\{[\s\S]*?\"recent_(?:patients|topics)\"[\s\S]*?\}\s*\n?```",
    re.IGNORECASE,
)
RECENT_PREFS_JSON_BARE_RE = re.compile(
    r"\{[\s\S]*?\"recent_(?:patients|topics)\"[\s\S]*?\"recent_(?:patients|topics)\"[\s\S]*?\}",
    re.IGNORECASE,
)
RECENT_PREFS_JSON_INCOMPLETE_FENCE_RE = re.compile(
    r"```json[\s\S]*?\"recent_(?:patients|topics)\"[\s\S]*$",
    re.IGNORECASE,
)
RECENT_PREFS_JSON_INCOMPLETE_BARE_RE = re.compile(
    r"\{[\s\S]*?\"recent_(?:patients|topics)\"[\s\S]*$",
    re.IGNORECASE,
)


def _strip_context_block(content: str) -> str:
    """移除【系统上下文】…偏好文件提示块。"""
    start = content.find(CONTEXT_START_MARKER)
    if start == -1:
        return content
    end_idx = content.find(CONTEXT_END_MARKER, start)
    if end_idx == -1:
        return content[:start].rstrip()
    after = content[end_idx + len(CONTEXT_END_MARKER) :].lstrip()
    return (content[:start] + after).lstrip()


def _looks_like_leaked_patient_summary_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("```"):
        return True
    if stripped.startswith("**") or stripped.startswith("- ") or stripped.startswith("* "):
        return True
    if stripped.startswith("当前问诊患者姓名"):
        return True
    if "的信息如下" in stripped:
        return True
    return False


def _strip_internal_notice_block(content: str) -> str:
    """移除【重要】内部提示、患者姓名规则及误复述的患者摘要。"""
    start = content.find(INTERNAL_NOTICE_MARKER)
    if start == -1:
        return content

    search_from = start + len(INTERNAL_NOTICE_MARKER)
    json_match = RECENT_PREFS_JSON_FENCE_RE.search(content, search_from)
    if json_match:
        end = json_match.end()
        after = content[end:].lstrip()
        return (content[:start] + after).lstrip()

    info_idx = content.find(PATIENT_INFO_HEADER, search_from)
    if info_idx != -1:
        pos = info_idx + len(PATIENT_INFO_HEADER)
        while pos < len(content) and content[pos] in "：:\n\r \t":
            pos += 1
        while pos < len(content):
            line_end = content.find("\n", pos)
            if line_end == -1:
                line_end = len(content)
            line = content[pos:line_end]
            if not line.strip():
                pos = line_end + 1 if line_end < len(content) else len(content)
                continue
            if _looks_like_leaked_patient_summary_line(line):
                pos = line_end + 1 if line_end < len(content) else len(content)
                continue
            break
        after = content[pos:].lstrip()
        return (content[:start] + after).lstrip()

    end_idx = content.find(INTERNAL_NOTICE_END, search_from)
    if end_idx == -1:
        return content[:start].rstrip()

    end = end_idx + len(INTERNAL_NOTICE_END)
    rest = content[end:]
    trimmed = rest.lstrip()
    if trimmed.startswith("当前问诊患者姓名"):
        line_end = rest.find("\n", len(rest) - len(trimmed))
        if line_end != -1:
            end = end + line_end + 1
        else:
            end = len(content)
    after = content[end:].lstrip()
    return (content[:start] + after).lstrip()


def _strip_recent_preferences_json(content: str) -> str:
    """移除 recent_patients / recent_topics 元数据 JSON 块（含未闭合流式片段）。"""
    cleaned = RECENT_PREFS_JSON_FENCE_RE.sub("", content)
    cleaned = RECENT_PREFS_JSON_BARE_RE.sub("", cleaned)
    cleaned = RECENT_PREFS_JSON_INCOMPLETE_FENCE_RE.sub("", cleaned)
    cleaned = RECENT_PREFS_JSON_INCOMPLETE_BARE_RE.sub("", cleaned)
    return re.sub(r"[`\s]+$", "", cleaned)


def strip_system_context_from_response(content: str) -> str:
    """从模型回复中移除误复述的内部会话上下文。"""
    cleaned = _strip_context_block(content)
    while True:
        next_cleaned = _strip_internal_notice_block(cleaned)
        next_cleaned = _strip_recent_preferences_json(next_cleaned)
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    return cleaned.strip()


def _format_patient_rule(ctx: "DoctorContext") -> str:
    if not ctx.patient_name:
        return ""
    return (
        f"\n当前问诊患者姓名为「{ctx.patient_name}」。"
        "向医生提及当前患者时必须使用该姓名，"
        "禁止根据 patient_slug 推断或编造姓名（例如 slug 含 zhang-san 不等于「张三」）。"
    )


def format_doctor_context_display(ctx: "DoctorContext") -> str:
    """供 trace 面板展示的会话上下文（与用户可见回复分离）。"""
    patient_lines = ""
    if ctx.patient_slug or ctx.patient_name:
        if ctx.patient_name:
            demo = ctx.patient_name
            if ctx.patient_gender and ctx.patient_age is not None:
                demo += f"（{ctx.patient_gender}，{ctx.patient_age}岁）"
            patient_lines += f"当前患者: {demo}\n"
        if ctx.patient_slug:
            patient_lines += f"patient_slug: {ctx.patient_slug}\n"
        if ctx.patient_chief_complaint:
            patient_lines += f"主诉: {ctx.patient_chief_complaint}\n"
    return (
        f"【系统上下文】\n"
        f"doctor_id: {ctx.doctor_id}\n"
        f"doctor_name: {ctx.doctor_name}\n"
        f"department: {ctx.department}\n"
        f"{patient_lines}"
        f"医生偏好文件: /memories/{ctx.doctor_id}/preferences.md\n"
        f"\n{CONTEXT_END_MARKER}\n\n"
        f"{INTERNAL_NOTICE_MARKER}，仅供你理解当前环境。"
        "请勿在回复中复述、引用或展示上述内容；"
        f"{INTERNAL_NOTICE_END}"
        f"{_format_patient_rule(ctx)}"
    )


def format_doctor_context_system_prompt(ctx: "DoctorContext") -> str:
    """注入 Agent 的系统提示（要求勿向用户复述）。"""
    return format_doctor_context_display(ctx)
