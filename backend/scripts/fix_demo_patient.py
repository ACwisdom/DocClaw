"""恢复演示患者 patient-zhang-san 为王浩然。"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models import ConsultMessage, FollowUpPlan, Patient

db = SessionLocal()
try:
    p = db.query(Patient).filter(Patient.slug == "patient-zhang-san").first()
    if not p:
        print("未找到 patient-zhang-san")
    else:
        p.name = "王浩然"
        p.age = 26
        for msg in db.query(ConsultMessage).filter(ConsultMessage.patient_id == p.id):
            if msg.content.startswith("已进入"):
                msg.content = (
                    f"已进入 {p.name} 的问诊工作台。你可以开始记录对话、上传资料或启动录音，"
                    "门诊病历会持续同步整理。"
                )
            elif "男" in msg.content and "岁" in msg.content:
                msg.content = re.sub(
                    r"[\u4e00-\u9fff]+，男，\d+ 岁",
                    f"{p.name}，男，{p.age} 岁",
                    msg.content,
                    count=1,
                )
        for plan in db.query(FollowUpPlan).filter(FollowUpPlan.patient_id == p.id):
            if " - " in plan.title:
                suffix = plan.title.split(" - ", 1)[1]
                plan.title = f"{p.name} - {suffix}"
        db.commit()
        print(f"已恢复演示患者: {p.name}, {p.age}岁")
finally:
    db.close()
