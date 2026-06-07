"""按性别与年龄段生成符合中文命名习惯的真实姓名（合成数据）。"""

from __future__ import annotations

import random

SURNAMES = (
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
    "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
    "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎",
)

# 18–35 岁常见名
MALE_YOUTH = (
    "浩然", "子轩", "宇轩", "梓豪", "俊杰", "明轩", "博文", "逸飞",
    "晨阳", "浩宇", "一鸣", "泽宇", "皓轩", "梓睿", "宇航", "子墨",
    "嘉懿", "铭泽", "瑞霖", "旭尧",
)
FEMALE_YOUTH = (
    "雨婷", "欣怡", "梓涵", "思琪", "晓彤", "佳怡", "诗涵", "梦琪",
    "心怡", "语桐", "可馨", "雅雯", "静怡", "紫萱", "若曦", "思妍",
    "雨萱", "佳宁", "诗雨", "晓月",
)

# 36–55 岁
MALE_MIDDLE = (
    "伟强", "志刚", "海涛", "明辉", "建军", "文杰", "国平", "永强",
    "振华", "志远", "文博", "俊峰", "明德", "国强", "海涛", "立军",
    "文斌", "建平", "洪涛", "天宇",
)
FEMALE_MIDDLE = (
    "秀英", "丽华", "红梅", "晓敏", "淑娟", "丽萍", "美玲", "静娴",
    "慧芳", "燕玲", "春梅", "晓霞", "桂兰", "玉兰", "秀珍", "淑华",
    "雅琴", "慧敏", "佩君", "彩霞",
)

# 56 岁及以上
MALE_SENIOR = (
    "建国", "志强", "文光", "德明", "国栋", "永年", "振华", "明远",
    "文斌", "卫东", "金水", "启明", "维正", "宝善", "福禄", "守仁",
    "庆华", "顺发", "有才", "长庚",
)
FEMALE_SENIOR = (
    "淑芬", "桂英", "玉兰", "秀兰", "淑华", "秀芳", "玉梅", "美华",
    "兰英", "淑珍", "佩英", "月娥", "慧君", "素珍", "凤英", "瑞珍",
    "巧云", "爱华", "春桃", "秋香",
)


YOUTH_AGE_MIN = 18
YOUTH_AGE_MAX = 35
YOUTH_RATIO_MIN = 1 / 3
YOUTH_RATIO_MAX = 1 / 2


def is_youth_age(age: int) -> bool:
    """18–35 岁视为年轻患者（与姓名生成年龄段一致）。"""
    return YOUTH_AGE_MIN <= age <= YOUTH_AGE_MAX


def _era(age: int) -> str:
    if age <= YOUTH_AGE_MAX:
        return "youth"
    if age < 56:
        return "middle"
    return "senior"


def _given_pool(gender: str, age: int) -> tuple[str, ...]:
    era = _era(age)
    if gender == "男":
        if era == "youth":
            return MALE_YOUTH
        if era == "middle":
            return MALE_MIDDLE
        return MALE_SENIOR
    if era == "youth":
        return FEMALE_YOUTH
    if era == "middle":
        return FEMALE_MIDDLE
    return FEMALE_SENIOR


def generate_patient_name(
    gender: str,
    age: int,
    used: set[str] | None = None,
    *,
    rng: random.Random | None = None,
) -> str:
    """生成与性别、年龄匹配的姓名，尽量避免重复。"""
    r = rng or random
    used = used or set()
    pool = _given_pool(gender, age)

    for _ in range(200):
        name = r.choice(SURNAMES) + r.choice(pool)
        if name not in used:
            used.add(name)
            return name

    # 极低概率撞名：加数字后缀式中间字
    base = r.choice(SURNAMES) + r.choice(pool)
    suffix = 0
    while f"{base}{suffix}" in used:
        suffix += 1
    name = base if suffix == 0 else f"{base[0]}{base[1]}{suffix}"
    used.add(name)
    return name


def rebalance_patient_age_distribution(
    db,
    *,
    youth_ratio: float | None = None,
    rng: random.Random | None = None,
) -> dict[str, int]:
    """调整患者年龄，使年轻患者占比落在 [1/3, 1/2]。"""
    from .models import FollowUpPlan, Patient

    r = rng or random
    if youth_ratio is None:
        youth_ratio = r.uniform(YOUTH_RATIO_MIN, YOUTH_RATIO_MAX)

    preserved_slugs = {"patient-zhang-san"}
    all_patients = db.query(Patient).order_by(Patient.queue_order).all()
    adjustable = [p for p in all_patients if p.slug not in preserved_slugs]
    n = len(adjustable)
    if n == 0:
        return {"total": len(all_patients), "updated": 0, "youth_count": 0, "youth_ratio": 0.0}

    youth_min_count = int(n * YOUTH_RATIO_MIN + 0.999)  # ceil(n/3)
    youth_max_count = int(n * YOUTH_RATIO_MAX + 0.5)  # round(n/2)
    target_youth = int(n * youth_ratio + 0.5)
    target_youth = max(youth_min_count, min(target_youth, youth_max_count))

    youth = [p for p in adjustable if is_youth_age(p.age)]
    non_youth = [p for p in adjustable if not is_youth_age(p.age)]
    updated = 0
    used_names: set[str] = {p.name for p in all_patients}

    def _set_youth(patient: Patient) -> None:
        nonlocal updated
        old_name = patient.name
        patient.age = r.randint(YOUTH_AGE_MIN, YOUTH_AGE_MAX)
        used_names.discard(old_name)
        patient.name = generate_patient_name(patient.gender, patient.age, used_names)
        updated += 1

    def _set_non_youth(patient: Patient) -> None:
        nonlocal updated
        old_name = patient.name
        patient.age = r.randint(36, 75)
        used_names.discard(old_name)
        patient.name = generate_patient_name(patient.gender, patient.age, used_names)
        updated += 1

    need = target_youth - len(youth)
    if need > 0:
        r.shuffle(non_youth)
        for patient in non_youth[:need]:
            _set_youth(patient)
    elif need < 0:
        r.shuffle(youth)
        for patient in youth[: -need]:
            _set_non_youth(patient)

    for plan in db.query(FollowUpPlan).all():
        patient = db.query(Patient).filter(Patient.id == plan.patient_id).first()
        if patient and " - " in plan.title:
            suffix = plan.title.split(" - ", 1)[1]
            plan.title = f"{patient.name} - {suffix}"

    db.commit()

    all_patients = db.query(Patient).all()
    youth_count = sum(1 for p in all_patients if is_youth_age(p.age))
    return {
        "total": len(all_patients),
        "updated": updated,
        "youth_count": youth_count,
        "youth_ratio": round(youth_count / n, 3),
        "target_youth": target_youth,
    }


def fix_all_patient_names(db) -> int:
    """按现有性别、年龄重生成全部患者姓名，并同步随访计划标题前缀。"""
    from .models import FollowUpPlan, Patient

    used: set[str] = set()
    count = 0
    for patient in db.query(Patient).order_by(Patient.queue_order).all():
        patient.name = generate_patient_name(patient.gender, patient.age, used)
        count += 1

    for plan in db.query(FollowUpPlan).all():
        patient = db.query(Patient).filter(Patient.id == plan.patient_id).first()
        if patient and " - " in plan.title:
            suffix = plan.title.split(" - ", 1)[1]
            plan.title = f"{patient.name} - {suffix}"

    db.commit()
    return count
