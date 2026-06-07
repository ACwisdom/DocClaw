#!/usr/bin/env python3
"""
DocClaw Phase 5 端到端验收脚本。

对应 HARNESS_PLAN.md 第 13 节 6 步演示，分三档运行：

  py -3.11 scripts/e2e_acceptance.py              # 基础设施 + 业务 API（无需 LLM）
  py -3.11 scripts/e2e_acceptance.py --with-llm   # 含 Skill 流式短路
  py -3.11 scripts/e2e_acceptance.py --with-agent # 含 Agent API 冒烟（需 LLM + Harness）

前置：Medical API :8000 已启动；--with-agent 另需 start_agent.py（:8090/:8001）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MEDICAL_BASE = os.getenv("MEDICAL_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
AGENT_BASE = os.getenv("AGENT_API_BASE_URL", "http://127.0.0.1:8090/api").rstrip("/")
DEMO_PATIENT_SLUG = os.getenv("DEMO_PATIENT_SLUG", "patient-zhang-san")

PASS = 0
FAIL = 0
SKIP = 0


def ok(step: str, detail: str = "") -> None:
    global PASS
    PASS += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [PASS] {step}{suffix}")


def fail(step: str, detail: str = "") -> None:
    global FAIL
    FAIL += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [FAIL] {step}{suffix}")


def skip(step: str, reason: str) -> None:
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {step} — {reason}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check_health(client: httpx.Client) -> bool:
    section("0. 服务健康检查")
    all_ok = True

    try:
        r = client.get(f"{MEDICAL_BASE.replace('/api', '')}/api/health", timeout=5)
        if r.status_code == 200:
            ok("Medical API :8000")
        else:
            fail("Medical API :8000", f"status={r.status_code}")
            all_ok = False
    except Exception as exc:
        fail("Medical API :8000", str(exc))
        all_ok = False

    try:
        r = client.get("http://127.0.0.1:8090/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            ok("Agent API :8090", f"agent_ready={data.get('agent_ready')}")
        else:
            skip("Agent API :8090", f"status={r.status_code}（--with-agent 时需要）")
    except Exception:
        skip("Agent API :8090", "未启动（--with-agent 时需要）")

    return all_ok


def step1_patient_summary(client: httpx.Client) -> None:
    section("1. 待接诊统计（演示：今天多少待接诊？）")
    try:
        r = client.get(f"{MEDICAL_BASE}/patients/summary", timeout=10)
        r.raise_for_status()
        data = r.json()
        waiting = data.get("waiting", 0)
        ok("patient_summary", f"待接诊={waiting}, 问诊中={data.get('consulting')}, 已完成={data.get('completed')}")
    except Exception as exc:
        fail("patient_summary", str(exc))


def step2_patient_detail(client: httpx.Client) -> str | None:
    section("2. 患者详情与检查（演示：主诉 + 检查结果）")
    try:
        r = client.get(f"{MEDICAL_BASE}/patients/{DEMO_PATIENT_SLUG}", timeout=10)
        r.raise_for_status()
        p = r.json()
        ok(
            "patient_get",
            f"{p.get('name')} / 主诉={p.get('chief_complaint', '')[:30]}…",
        )
        if p.get("completed_exams"):
            ok("his_get_labs 数据源", p["completed_exams"][:60])
        else:
            skip("his_get_labs 数据源", "无 completed_exams")
        return p.get("id")
    except Exception as exc:
        fail("patient_get", str(exc))
        return None


def step3_skill_stream(client: httpx.Client) -> None:
    section("3. Skill 模式病历结构化短路")
    if not os.getenv("LLM_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
        skip("consult stream", "未配置 LLM_API_KEY / DEEPSEEK_API_KEY")
        return

    try:
        skills = client.get(f"{MEDICAL_BASE}/skills", timeout=10).json()
        default_skill = next((s for s in skills if s.get("is_default")), None)
        skill_id = default_skill["id"] if default_skill else None

        with client.stream(
            "POST",
            f"{MEDICAL_BASE}/consult/{DEMO_PATIENT_SLUG}/messages/stream",
            json={"content": "请根据当前问诊整理门诊病历", "skill_id": skill_id},
            timeout=120,
        ) as resp:
            if resp.status_code != 200:
                fail("consult stream", f"status={resp.status_code}")
                return

            got_structured = False
            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    part, buffer = buffer.split("\n\n", 1)
                    event_name = ""
                    data_str = ""
                    for line in part.split("\n"):
                        if line.startswith("event:"):
                            event_name = line[6:].strip()
                        elif line.startswith("data:"):
                            data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        event_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if event_name == "structured" or "structured_data" in event_data:
                        got_structured = True

            if got_structured:
                ok("Skill 短路", "收到 structured / medical_record 事件")
            else:
                fail("Skill 短路", "未收到结构化病历事件")

    except Exception as exc:
        fail("consult stream", str(exc))


def step4_followup_plan(client: httpx.Client, patient_id: str | None) -> str | None:
    section("4. 随访计划创建（API 验证；HITL 见 DEMO.md 手动演示）")
    if not patient_id:
        skip("followup_create_plan", "无 patient_id")
        return None

    title = f"验收演示-2周复查-{int(time.time())}"
    scheduled = (datetime.utcnow() + timedelta(days=14)).isoformat()
    try:
        r = client.post(
            f"{MEDICAL_BASE}/followup",
            json={
                "patient_id": patient_id,
                "title": title,
                "description": "Phase 5 验收自动创建",
                "tasks": [
                    {
                        "title": "复查提醒",
                        "description": "门诊复查",
                        "scheduled_at": scheduled,
                    }
                ],
            },
            timeout=15,
        )
        r.raise_for_status()
        plan = r.json()
        ok("followup_create_plan", f"plan_id={plan.get('id')}, tasks={len(plan.get('tasks', []))}")
        return plan.get("id")
    except Exception as exc:
        fail("followup_create_plan", str(exc))
        return None


def step5_scheduler_notification(client: httpx.Client, patient_id: str | None) -> None:
    section("5. 调度器执行随访 → 产生通知")
    if not patient_id:
        skip("scheduler", "无 patient_id")
        return

    from app.database import SessionLocal
    from app.models import FollowUpPlan, FollowUpTask, Notification, TaskStatus
    from app.services.task_scheduler import execute_pending_tasks

    db = SessionLocal()
    try:
        before_count = db.query(Notification).count()
        plan = FollowUpPlan(
            patient_id=patient_id,
            doctor_id="doctor-li",
            title="调度器验收计划",
            description="Phase 5 自动验收",
        )
        db.add(plan)
        db.flush()
        db.add(
            FollowUpTask(
                plan_id=plan.id,
                title="到期复查任务",
                description="应立即被调度器执行",
                scheduled_at=datetime.utcnow() - timedelta(minutes=5),
                status=TaskStatus.PENDING,
            )
        )
        db.commit()

        execute_pending_tasks()

        db.expire_all()
        task = db.query(FollowUpTask).filter(FollowUpTask.plan_id == plan.id).first()
        after_count = db.query(Notification).count()

        if task and task.status == TaskStatus.COMPLETED:
            ok("scheduler 执行任务", task.result[:80])
        else:
            fail("scheduler 执行任务", f"status={getattr(task, 'status', None)}")

        if after_count > before_count:
            ok("通知产生", f"notifications +{after_count - before_count}")
        else:
            fail("通知产生", "调度后未新增通知")
    except Exception as exc:
        fail("scheduler", str(exc))
    finally:
        db.close()


def step6_pending_tasks(client: httpx.Client) -> None:
    section("6. 待执行随访查询")
    try:
        r = client.get(f"{MEDICAL_BASE}/followup/tasks/pending", timeout=10)
        r.raise_for_status()
        tasks = r.json()
        ok("followup_pending_tasks", f"待办 {len(tasks)} 项")
    except Exception as exc:
        fail("followup_pending_tasks", str(exc))


def step_agent_smoke(client: httpx.Client) -> None:
    section("Agent 冒烟（演示步骤 1–2 的 Harness 通路）")
    if not os.getenv("LLM_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
        skip("agent chat", "未配置 LLM")
        return

    try:
        health = client.get("http://127.0.0.1:8090/health", timeout=5).json()
        if not health.get("agent_ready"):
            skip("agent chat", f"Agent 未就绪: {health.get('agent_error')}")
            return
    except Exception as exc:
        skip("agent chat", str(exc))
        return

    try:
        with client.stream(
            "POST",
            f"{AGENT_BASE}/agent/chat",
            json={
                "message": "今天有多少待接诊患者？简要回答。",
                "patient_slug": DEMO_PATIENT_SLUG,
                "doctor_id": "doctor-li",
            },
            timeout=180,
        ) as resp:
            if resp.status_code != 200:
                fail("agent chat", f"status={resp.status_code}")
                return

            got_token = False
            got_done = False
            buffer = ""
            for chunk in resp.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    part, buffer = buffer.split("\n\n", 1)
                    for line in part.split("\n"):
                        if not line.startswith("data:"):
                            continue
                        try:
                            data = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if data.get("type") == "token":
                            got_token = True
                        if data.get("type") == "done":
                            got_done = True

            if got_token and got_done:
                ok("Agent SSE 对话", "token + done")
            elif got_done:
                ok("Agent SSE 对话", "done（无 token，可能工具直返）")
            else:
                fail("Agent SSE 对话", "未收到完整 SSE")
    except Exception as exc:
        fail("agent chat", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="DocClaw Phase 5 验收脚本")
    parser.add_argument("--with-llm", action="store_true", help="运行 Skill 流式步骤（需 LLM Key）")
    parser.add_argument("--with-agent", action="store_true", help="运行 Agent API 冒烟（需 Harness + LLM）")
    args = parser.parse_args()

    print("DocClaw Phase 5 端到端验收")
    print(f"  Medical API: {MEDICAL_BASE}")
    print(f"  Demo patient: {DEMO_PATIENT_SLUG}")

    with httpx.Client() as client:
        if not check_health(client):
            print("\n请先启动 Medical API: uvicorn app.main:app --port 8000")
            return 1

        step1_patient_summary(client)
        patient_id = step2_patient_detail(client)

        if args.with_llm:
            step3_skill_stream(client)
        else:
            skip("Skill 流式短路", "加 --with-llm 启用")

        step4_followup_plan(client, patient_id)
        step5_scheduler_notification(client, patient_id)
        step6_pending_tasks(client)

        if args.with_agent:
            step_agent_smoke(client)
        else:
            skip("Agent 冒烟", "加 --with-agent 启用")

    print(f"\n结果: PASS={PASS} FAIL={FAIL} SKIP={SKIP}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
