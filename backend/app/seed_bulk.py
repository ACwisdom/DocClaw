"""批量生成高仿真门诊演示数据（合成数据，非真实患者隐私）。

用法:
    cd backend
    python -m app.seed_bulk --patients 500
    python -m app.seed_bulk --patients 1000 --with-messages --with-followups
    python -m app.seed_bulk --reset --patients 800
"""

from __future__ import annotations

import argparse
import json
import random
import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .models import (
    ConsultMessage,
    Doctor,
    FollowUpPlan,
    FollowUpTask,
    Notification,
    Patient,
    Priority,
    Skill,
    SkillExecutionLog,
    SkillStatus,
    StoreSkill,
    TaskStatus,
    TaskType,
    VisitStatus,
    VisitType,
)
from .patient_names import (
    YOUTH_AGE_MAX,
    YOUTH_AGE_MIN,
    generate_patient_name,
    rebalance_patient_age_distribution,
)
from .seed import seed_database

# ---------------------------------------------------------------------------
# 时间随机化工具
# ---------------------------------------------------------------------------


def random_clinic_datetime(*, past_days_max: int = 0, future_days_max: int = 0) -> datetime:
    """生成带随机时分秒的门诊时段时间（8:00–18:00 UTC+0 模拟）。"""
    now = datetime.utcnow()
    day_shift = 0
    if past_days_max > 0 and future_days_max > 0:
        day_shift = random.randint(-past_days_max, future_days_max)
    elif past_days_max > 0:
        day_shift = -random.randint(1, past_days_max)
    elif future_days_max > 0:
        day_shift = random.randint(1, future_days_max)

    base = now + timedelta(days=day_shift)
    return base.replace(
        hour=random.randint(8, 17),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=random.randint(0, 999999),
    )


def random_future_schedule(days_min: int = 1, days_max: int = 45) -> datetime:
    now = datetime.utcnow()
    return now + timedelta(
        days=random.randint(days_min, days_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
        microseconds=random.randint(0, 999999),
    )


def random_past_moment(days_min: int = 1, days_max: int = 90) -> datetime:
    now = datetime.utcnow()
    return now - timedelta(
        days=random.randint(days_min, days_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
        microseconds=random.randint(0, 999999),
    )


def fix_all_timestamps(db: Session) -> dict[str, int]:
    """将数据库中雷同的时间戳打散为互不相同且合理的值。"""
    stats = {
        "followup_tasks": 0,
        "followup_plans": 0,
        "consult_messages": 0,
        "notifications": 0,
        "skill_logs": 0,
        "skills": 0,
    }

    for task in db.query(FollowUpTask).all():
        if task.status == TaskStatus.COMPLETED:
            executed = random_past_moment(1, 45)
            task.executed_at = executed
            gap = timedelta(
                days=random.randint(0, 7),
                hours=random.randint(1, 72),
                minutes=random.randint(0, 59),
            )
            task.scheduled_at = executed - gap
        elif task.status == TaskStatus.CANCELLED:
            task.scheduled_at = random_future_schedule(1, 30)
            task.executed_at = None
        else:
            task.scheduled_at = random_future_schedule(1, 60)
            task.executed_at = None
        stats["followup_tasks"] += 1

    for plan in db.query(FollowUpPlan).all():
        tasks = sorted(plan.tasks, key=lambda t: t.scheduled_at)
        if tasks:
            earliest = min(t.scheduled_at for t in tasks)
            plan.created_at = earliest - timedelta(
                days=random.randint(0, 3),
                hours=random.randint(1, 48),
                minutes=random.randint(0, 59),
            )
        else:
            plan.created_at = random_past_moment(1, 90)
        stats["followup_plans"] += 1

    for patient in db.query(Patient).all():
        messages = (
            db.query(ConsultMessage)
            .filter(ConsultMessage.patient_id == patient.id)
            .order_by(ConsultMessage.id)
            .all()
        )
        base = random_past_moment(1, 120)
        offset_minutes = 0
        for msg in messages:
            offset_minutes += random.randint(1, 25)
            msg.created_at = base + timedelta(minutes=offset_minutes)
            stats["consult_messages"] += 1

    for note in db.query(Notification).all():
        note.created_at = random_past_moment(0, 45)
        stats["notifications"] += 1

    for log in db.query(SkillExecutionLog).all():
        log.created_at = random_past_moment(0, 60)
        stats["skill_logs"] += 1

    for skill in db.query(Skill).all():
        skill.created_at = random_clinic_datetime(past_days_max=120)
        stats["skills"] += 1

    db.commit()
    return stats


# ---------------------------------------------------------------------------
# 临床词库（来源于公开临床教材/指南常见表述，非真实患者记录）
# ---------------------------------------------------------------------------

CHIEF_COMPLAINTS = [
    ("反复咳嗽三周，伴午后低热", Priority.URGENT, VisitType.FIRST),
    ("发热伴咽痛四天，夜间咳嗽明显", Priority.NORMAL, VisitType.FIRST),
    ("高血压复查，晨起头晕并偶有气短", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("活动后气促两周，伴夜间胸闷", Priority.URGENT, VisitType.FIRST),
    ("夜间胸闷伴阵发性咳嗽五天", Priority.NORMAL, VisitType.FIRST),
    ("慢阻肺复诊，近期痰量增多", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("鼻塞流涕伴低热三天，咳嗽加重", Priority.NORMAL, VisitType.FIRST),
    ("慢性咳喘复查，夜间憋醒两次", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("乏力伴食欲下降一周，轻度干咳", Priority.NORMAL, VisitType.FIRST),
    ("咳嗽伴少量黄痰六天", Priority.NORMAL, VisitType.FIRST),
    ("间断胸痛伴心悸两天", Priority.URGENT, VisitType.FIRST),
    ("肺结节随访复查", Priority.NORMAL, VisitType.FOLLOWUP),
    ("过敏性咳嗽加重一周", Priority.NORMAL, VisitType.FOLLOWUP),
    ("发热退后仍胸闷气短", Priority.NORMAL, VisitType.FOLLOWUP),
    ("体检发现血压偏高，近期头痛", Priority.NORMAL, VisitType.FIRST),
    ("运动后喘息反复发作", Priority.NORMAL, VisitType.FIRST),
    ("夜间咳醒伴晨起咳痰", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("糖尿病合并咳嗽复诊", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("持续咽痒干咳十天", Priority.NORMAL, VisitType.FIRST),
    ("肺部感染治疗后复查", Priority.NORMAL, VisitType.FOLLOWUP),
    ("咯血半天，量约5ml", Priority.URGENT, VisitType.FIRST),
    ("胸闷气促加重三天，不能平卧", Priority.URGENT, VisitType.FIRST),
    ("哮喘控制不佳，吸入剂使用后仍喘息", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("职业性粉尘接触后咳嗽两月", Priority.NORMAL, VisitType.FIRST),
    ("戒烟后仍持续干咳八周", Priority.NORMAL, VisitType.FIRST),
    ("上呼吸道感染后咳嗽迁延不愈", Priority.NORMAL, VisitType.FOLLOWUP),
    ("双下肢水肿伴活动耐量下降", Priority.URGENT, VisitType.FIRST),
    ("发热最高39.2℃，伴寒战及全身酸痛", Priority.URGENT, VisitType.FIRST),
    ("支气管扩张症复诊，痰液增多", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("间质性肺病随访，评估肺功能", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("OSA 复查，日间嗜睡未改善", Priority.CHRONIC, VisitType.FOLLOWUP),
    ("胸膜性胸痛，深呼吸时加重", Priority.NORMAL, VisitType.FIRST),
    ("流感样症状三天，高热伴肌肉酸痛", Priority.NORMAL, VisitType.FIRST),
    ("COPD 急性加重，黄脓痰增多", Priority.URGENT, VisitType.FOLLOWUP),
    ("体检胸片异常，要求进一步评估", Priority.NORMAL, VisitType.FIRST),
    ("长期吸烟，慢性咳嗽咳痰十年", Priority.CHRONIC, VisitType.FIRST),
    ("接触花粉后喘息发作", Priority.NORMAL, VisitType.FIRST),
    ("结核接触史，低热盗汗两周", Priority.URGENT, VisitType.FIRST),
    ("肺栓塞抗凝治疗后复查", Priority.NORMAL, VisitType.FOLLOWUP),
    ("胸腔积液穿刺后随访", Priority.NORMAL, VisitType.FOLLOWUP),
]

EXAM_TEMPLATES = [
    "血常规：WBC {wbc}×10⁹/L，NEUT {neut}%；CRP {crp} mg/L",
    "血压 {sys}/{dia} mmHg，心率 {hr} 次/分",
    "胸部CT：{ct}",
    "胸片：{xray}",
    "肺功能：FEV1 {fev1}% 预计值，FEV1/FVC {ratio}%",
    "血气分析：PaO2 {pao2} mmHg，PaCO2 {paco2} mmHg",
    "D-二聚体 {ddimer} mg/L",
    "痰培养：{culture}",
    "心电图：{ecg}",
    "HbA1c {hba1c}%",
    "降钙素原 {pct} ng/ml",
    "",
]

CT_FINDINGS = [
    "双肺散在条索影",
    "右下肺斑片状渗出",
    "左肺上叶5mm磨玻璃结节",
    "肺气肿改变，肺大疱",
    "支气管壁增厚",
    "未见明显实质性病变",
    "少量胸腔积液",
    "肺纹理增粗",
]

XRAY_FINDINGS = [
    "心影不大，双肺纹理增粗",
    "右下肺片状影",
    "未见明显异常",
    "肺动脉段略突出",
    "肋膈角钝",
]

ECG_FINDINGS = [
    "窦性心律",
    "ST-T 轻度改变",
    "左心室高电压",
    "偶发房性早搏",
]

CULTURE_FINDINGS = [
    "肺炎链球菌",
    "未检出致病菌",
    "流感嗜血杆菌",
    "卡他莫拉菌",
]

DOCTOR_TEMPLATES = [
    ("doctor-li", "李医生", "主治医师", "呼吸内科门诊"),
    ("doctor-wang", "王医生", "副主任医师", "呼吸内科门诊"),
    ("doctor-zhang", "张医生", "主任医师", "呼吸与危重症医学科"),
    ("doctor-chen", "陈医生", "主治医师", "全科医学科"),
    ("doctor-liu", "刘医生", "住院医师", "呼吸内科门诊"),
]

DOCTOR_DIALOGUES = [
    ("doctor", "患者主诉{complaint}，请问持续多久了？"),
    ("assistant", "根据目前信息，建议完善血常规、CRP 及胸部影像学检查，并记录体温变化曲线。"),
    ("doctor", "查体：双肺呼吸音{lung_sound}，未闻及明显干湿啰音。"),
    ("assistant", "已记录查体结果。如需生成门诊病历，请说「帮我输出病历」。"),
    ("doctor", "既往有{history}，无药物过敏史。"),
    ("assistant", "建议关注{focus}，必要时考虑{exam}进一步评估。"),
]

HISTORIES = ["高血压", "2型糖尿病", "慢阻肺", "支气管哮喘", "冠心病", "无特殊"]
FOCUS_ITEMS = ["感染指标", "心功能", "气道高反应", "肺结节变化", "血糖控制"]
EXAM_SUGGESTIONS = ["胸部CT", "肺功能检查", "动态心电图", "痰培养", "支气管舒张试验"]

FOLLOWUP_TITLES = [
    "复查血常规与CRP",
    "电话随访 - 症状变化",
    "复查胸部CT",
    "肺功能复测",
    "用药依从性随访",
    "慢病管理宣教",
]


def _sample_patient_age(priority: Priority) -> int:
    """采样年龄，年轻患者（18–35）占比约 40%（落在 1/3–1/2 区间）。"""
    roll = random.random()
    if priority == Priority.CHRONIC:
        if roll < 0.22:
            return random.randint(YOUTH_AGE_MIN, YOUTH_AGE_MAX)
        if roll < 0.62:
            return random.randint(36, 58)
        return random.randint(59, 85)

    if roll < 0.40:
        return random.randint(YOUTH_AGE_MIN, YOUTH_AGE_MAX)
    if roll < 0.72:
        return random.randint(36, 55)
    return random.randint(56, 88)


def _slugify(name: str, index: int) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff-]", "", name.lower())
    return f"patient-{base}-{index}"


def _random_name(age: int, used: set[str]) -> tuple[str, str]:
    gender = random.choice(["男", "女"])
    name = generate_patient_name(gender, age, used)
    return name, gender


def _random_exams() -> str:
    if random.random() < 0.35:
        return ""
    tpl = random.choice(EXAM_TEMPLATES)
    if not tpl:
        return ""
    return tpl.format(
        wbc=round(random.uniform(4.0, 15.0), 1),
        neut=random.randint(55, 85),
        crp=round(random.uniform(0.5, 80.0), 1),
        sys=random.randint(110, 170),
        dia=random.randint(65, 105),
        hr=random.randint(60, 105),
        ct=random.choice(CT_FINDINGS),
        xray=random.choice(XRAY_FINDINGS),
        fev1=random.randint(45, 95),
        ratio=random.randint(55, 85),
        pao2=random.randint(65, 98),
        paco2=random.randint(32, 48),
        ddimer=round(random.uniform(0.1, 2.5), 2),
        culture=random.choice(CULTURE_FINDINGS),
        ecg=random.choice(ECG_FINDINGS),
        hba1c=round(random.uniform(5.2, 9.5), 1),
        pct=round(random.uniform(0.01, 1.5), 2),
    )


def _random_status_weights() -> VisitStatus:
    r = random.random()
    if r < 0.55:
        return VisitStatus.WAITING
    if r < 0.70:
        return VisitStatus.CONSULTING
    return VisitStatus.COMPLETED


def _key_notes(complaint: str, exams: str) -> str:
    parts = []
    if "热" in complaint or "感染" in complaint:
        parts.append("需关注感染指标")
    if "气促" in complaint or "胸闷" in complaint:
        parts.append("评估心肺功能")
    if "血压" in complaint or "头晕" in complaint:
        parts.append("监测血压变化")
    if exams:
        parts.append("已有部分检查结果")
    return "；".join(parts) if parts else random.choice(["首次就诊", "复诊随访", "慢病管理"])


def _ensure_base_seed(db: Session) -> Doctor:
    seed_database(db)
    doctor = db.query(Doctor).first()
    if not doctor:
        raise RuntimeError("基础种子数据初始化失败")
    return doctor


def _ensure_extra_doctors(db: Session) -> None:
    for doc_id, name, title, dept in DOCTOR_TEMPLATES:
        if db.query(Doctor).filter(Doctor.id == doc_id).first():
            continue
        db.add(
            Doctor(
                id=doc_id,
                name=name,
                title=title,
                department=dept,
                avatar=name[0],
            )
        )


def _reset_patient_data(db: Session) -> None:
    db.query(SkillExecutionLog).delete()
    db.query(ConsultMessage).delete()
    db.query(FollowUpTask).delete()
    db.query(FollowUpPlan).delete()
    db.query(Patient).delete()
    db.commit()


def generate_patients(
    db: Session,
    count: int,
    *,
    with_messages: bool = False,
    with_followups: bool = False,
    messages_per_patient: int = 4,
) -> dict[str, int]:
    doctor = _ensure_base_seed(db)
    _ensure_extra_doctors(db)
    db.flush()

    skill = (
        db.query(Skill)
        .filter(Skill.doctor_id == doctor.id, Skill.is_default.is_(True))
        .first()
    )
    skill_id = skill.id if skill else None

    existing_slugs = {p.slug for p in db.query(Patient.slug).all()}
    max_order = db.query(Patient.queue_order).order_by(Patient.queue_order.desc()).first()
    queue_start = (max_order[0] if max_order else 0) + 1

    stats = {"patients": 0, "messages": 0, "followup_plans": 0, "followup_tasks": 0}

    used_names: set[str] = set()

    for i in range(count):
        complaint_tpl = random.choice(CHIEF_COMPLAINTS)
        complaint, default_priority, default_vtype = complaint_tpl

        age = _sample_patient_age(default_priority)

        name, gender = _random_name(age, used_names)

        slug = _slugify(name, queue_start + i)
        while slug in existing_slugs:
            slug = f"{slug}-{random.randint(1000, 9999)}"
        existing_slugs.add(slug)

        exams = _random_exams()
        status = _random_status_weights()
        vtype = default_vtype if random.random() > 0.25 else (
            VisitType.FOLLOWUP if default_vtype == VisitType.FIRST else VisitType.FIRST
        )

        patient = Patient(
            slug=slug,
            name=name,
            gender=gender,
            age=age,
            chief_complaint=complaint,
            visit_type=vtype,
            status=status,
            priority=default_priority,
            queue_order=queue_start + i,
            completed_exams=exams,
            key_notes=_key_notes(complaint, exams),
            first_visit_note=random.choice(
                ["首次就诊", "复诊", "慢病随访", "急诊转门诊", "体检异常转诊", ""]
            ),
        )
        db.add(patient)
        db.flush()
        stats["patients"] += 1

        if with_messages and status != VisitStatus.WAITING:
            stats["messages"] += _add_consult_messages(
                db, patient, complaint, messages_per_patient
            )

        if with_followups and random.random() < 0.25:
            plan, tasks = _add_followup(db, patient, doctor.id, skill_id)
            stats["followup_plans"] += 1
            stats["followup_tasks"] += tasks

        if i > 0 and i % 200 == 0:
            db.commit()

    db.commit()
    return stats


def _add_consult_messages(
    db: Session, patient: Patient, complaint: str, count: int
) -> int:
    base_time = random_past_moment(1, 90)
    added = 0

    db.add(
        ConsultMessage(
            patient_id=patient.id,
            role="system",
            message_type="welcome",
            content=f"已进入 {patient.name} 的问诊工作台。",
            created_at=base_time,
        )
    )
    added += 1

    for j in range(min(count, len(DOCTOR_DIALOGUES))):
        role, tpl = DOCTOR_DIALOGUES[j]
        content = tpl.format(
            complaint=complaint,
            lung_sound=random.choice(["清", "略粗", "对称"]),
            history=random.choice(HISTORIES),
            focus=random.choice(FOCUS_ITEMS),
            exam=random.choice(EXAM_SUGGESTIONS),
        )
        db.add(
            ConsultMessage(
                patient_id=patient.id,
                role=role,
                content=content,
                created_at=base_time + timedelta(
                    minutes=sum(random.randint(2, 18) for _ in range(j + 1))
                ),
            )
        )
        added += 1

    return added


def _add_followup(
    db: Session, patient: Patient, doctor_id: str, skill_id: str | None
) -> tuple[FollowUpPlan, int]:
    plan = FollowUpPlan(
        patient_id=patient.id,
        doctor_id=doctor_id,
        title=f"{patient.name} - 门诊随访计划",
        description=patient.chief_complaint[:80],
        skill_id=skill_id,
        created_at=random_past_moment(1, 30),
    )
    db.add(plan)
    db.flush()

    task_count = random.randint(1, 3)
    used_times: set[str] = set()
    for k in range(task_count):
        status = random.choice(
            [TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        )
        if status == TaskStatus.COMPLETED:
            executed_at = random_past_moment(1, 20)
            scheduled_at = executed_at - timedelta(
                days=random.randint(0, 5),
                hours=random.randint(1, 48),
                minutes=random.randint(0, 59),
            )
        else:
            executed_at = None
            scheduled_at = random_future_schedule(3, 45)
            while scheduled_at.isoformat() in used_times:
                scheduled_at = random_future_schedule(3, 45)
            used_times.add(scheduled_at.isoformat())

        db.add(
            FollowUpTask(
                plan_id=plan.id,
                title=random.choice(FOLLOWUP_TITLES),
                description=f"针对「{patient.chief_complaint[:30]}」的随访任务",
                scheduled_at=scheduled_at,
                status=status,
                executed_at=executed_at,
            )
        )

    return plan, task_count


DEPARTMENT_SHARED_STORE_NAME_PREFIX = "科室共享技能包"


def purge_department_shared_store_skills(db: Session) -> dict[str, int]:
    """删除「科室共享技能包」类广场技能及已安装到个人的副本。"""
    pattern = f"{DEPARTMENT_SHARED_STORE_NAME_PREFIX}%"
    store_deleted = (
        db.query(StoreSkill)
        .filter(StoreSkill.name.like(pattern))
        .delete(synchronize_session=False)
    )
    skill_deleted = (
        db.query(Skill)
        .filter(Skill.name.like(pattern))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"store_skills": store_deleted, "personal_skills": skill_deleted}


def main() -> None:
    parser = argparse.ArgumentParser(description="批量生成 DocClaw 演示数据")
    parser.add_argument("--patients", type=int, default=500, help="新增患者数量")
    parser.add_argument("--reset", action="store_true", help="清空患者相关数据后重新生成")
    parser.add_argument("--with-messages", action="store_true", help="为非候诊患者生成对话")
    parser.add_argument("--with-followups", action="store_true", help="随机生成随访计划")
    parser.add_argument("--messages-per-patient", type=int, default=4)
    parser.add_argument("--fix-timestamps", action="store_true", help="打散数据库中雷同的时间戳")
    parser.add_argument(
        "--purge-department-store-skills",
        action="store_true",
        help="删除「科室共享技能包」类广场/个人技能",
    )
    parser.add_argument("--fix-names", action="store_true", help="按性别年龄重生成真实姓名")
    parser.add_argument(
        "--rebalance-ages",
        action="store_true",
        help="调整现有患者年龄，使年轻患者占比在 1/3–1/2",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.rebalance_ages:
            print("正在调整患者年龄分布…")
            stats = rebalance_patient_age_distribution(db)
            print("\n=== 年龄分布调整完成 ===")
            print(f"  患者总数: {stats['total']}")
            print(f"  更新人数: {stats['updated']}")
            print(f"  年轻患者: {stats['youth_count']} ({stats['youth_ratio']:.1%})")
            print(f"  目标年轻: {stats['target_youth']}")
            return

        if args.purge_department_store_skills:
            print("正在删除科室共享技能包…")
            stats = purge_department_shared_store_skills(db)
            print(f"  广场技能: {stats['store_skills']} 条")
            print(f"  个人技能: {stats['personal_skills']} 条")
            return

        if args.fix_names:
            from .patient_names import fix_all_patient_names

            print("正在重生成患者姓名…")
            count = fix_all_patient_names(db)
            print(f"已更新 {count} 名患者姓名")
            return

        if args.fix_timestamps:
            print("正在随机化时间戳…")
            stats = fix_all_timestamps(db)
            print("\n=== 时间戳修复完成 ===")
            for key, val in stats.items():
                print(f"  {key}: {val}")
            return

        if args.reset:
            print("正在清空患者相关数据…")
            _reset_patient_data(db)

        print(f"正在生成 {args.patients} 名患者…")
        stats = generate_patients(
            db,
            args.patients,
            with_messages=args.with_messages,
            with_followups=args.with_followups,
            messages_per_patient=args.messages_per_patient,
        )

        total_patients = db.query(Patient).count()
        total_messages = db.query(ConsultMessage).count()

        print("\n=== 生成完成 ===")
        print(f"本次新增患者: {stats['patients']}")
        print(f"本次新增消息: {stats['messages']}")
        print(f"本次新增随访计划: {stats['followup_plans']}")
        print(f"本次新增随访任务: {stats['followup_tasks']}")
        print(f"数据库合计患者: {total_patients}")
        print(f"数据库合计消息: {total_messages}")
        print(f"数据库文件: {engine.url.database}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
