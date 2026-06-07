from sqlalchemy.orm import Session

from ..models import Patient, Skill


def get_active_skill(db: Session, skill_id: str | None = None) -> Skill | None:
    if skill_id:
        return db.query(Skill).filter(Skill.id == skill_id, Skill.enabled == True).first()
    return (
        db.query(Skill)
        .filter(Skill.is_default == True, Skill.enabled == True)
        .first()
    )


def _extract_patient_from_system(system_message: str) -> dict[str, str]:
    fields = {
        "name": "患者",
        "gender": "未知",
        "age": "未知",
        "chief_complaint": "待补充",
        "completed_exams": "暂无",
        "key_notes": "待补充详细病史。",
    }
    for line in system_message.splitlines():
        line = line.strip()
        if line.startswith("- 姓名："):
            fields["name"] = line.split("：", 1)[1].strip()
        elif line.startswith("- 性别/年龄："):
            parts = line.split("：", 1)[1].strip().split("·")
            if len(parts) >= 2:
                fields["gender"] = parts[0].strip()
                fields["age"] = parts[1].replace("岁", "").strip()
        elif line.startswith("- 主诉："):
            fields["chief_complaint"] = line.split("：", 1)[1].strip()
        elif line.startswith("- 已完成检查："):
            fields["completed_exams"] = line.split("：", 1)[1].strip()
        elif line.startswith("- 重点提示："):
            fields["key_notes"] = line.split("：", 1)[1].strip()
    return fields


def _generate_mock_response(
    user_message: str,
    system_message: str,
    skill_name: str,
) -> str:
    patient = _extract_patient_from_system(system_message)
    name = patient["name"]
    gender = patient["gender"]
    age = patient["age"]
    chief_complaint = patient["chief_complaint"]
    completed_exams = patient["completed_exams"]
    key_notes = patient["key_notes"]

    if "病历" in user_message or "输出" in user_message:
        return f"""好的，基于当前问诊信息，为您整理**门诊病历**：

---

**门诊病历**

**姓名**：{name}　**性别**：{gender}　**年龄**：{age}岁

**主诉**：{chief_complaint}

**现病史**：患者自述{chief_complaint}。{key_notes}

**既往史**：待补充

**过敏史**：待补充

**查体**：待补充

**辅助检查**：{completed_exams}

**初步诊断**：待完善信息后确定

**处理意见**：待补充

---

> 由 **{skill_name}** 生成（规则模拟模式）。请继续补充信息后再次请求整理。"""

    if "随访" in user_message or "计划" in user_message:
        return f"""已为 **{name}** 生成随访计划建议：

1. **7天后** - 电话随访，了解症状变化
2. **14天后** - 复查相关检验指标
3. **1个月后** - 门诊复诊评估

可在「随访计划」页面确认并创建正式任务。"""

    if "检查" in user_message or "标红" in skill_name or "结果" in user_message:
        return f"""【{skill_name}】**检查回顾**

**患者**：{name}
**已完成检查**：{completed_exams}

**提示**：
- 请结合主诉「{chief_complaint}」关注异常指标
- 对未在上下文中出现的数值不做推断
- 建议医生核对原始报告后确认

> 规则模拟模式。配置 LLM API Key 后可获得更精准分析。"""

    return f"""【{skill_name}】已收到：「{user_message}」

当前患者 **{name}**（{gender} · {age}岁），主诉：{chief_complaint}。

您可以：
- 继续录入问诊内容
- 发送「帮我输出病历」生成门诊病历
- 发送「创建随访计划」生成随访建议
- 切换其他已启用技能处理专项任务

> 当前为规则模拟模式。在 `backend/.env` 配置 `LLM_API_KEY` 后将调用真实模型。"""


def generate_task_result(task_title: str, patient_name: str) -> str:
    return f"""【随访任务执行结果】

**任务**：{task_title}
**患者**：{patient_name}
**执行时间**：已自动执行

**结果摘要**：
- 任务已按计划完成
- 建议关注患者后续反馈
- 如有异常请及时安排复诊

> 此结果为 AI 辅助生成，请医生审核确认。"""
