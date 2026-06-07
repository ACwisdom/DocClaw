---
name: plan-create
version: "1.0.0"
description: >
  随访计划创建与执行 SOP。涵盖计划草稿、HITL 确认、任务编排与患者触达提醒。
tags: ["followup", "care-plan", "docclaw"]
---

# 随访计划创建 SOP

## 适用场景

- 医生要求为当前患者创建复查 / 复诊 / 慢病随访计划
- 查询待办随访任务并执行
- 生成患者触达提醒（`notification_create`）

关键词：随访、复查、提醒、触达、复诊、任务。

## 标准工作流

### 1. 确认患者

```
patient_get(slug) → 记录 patient_id（注意与 slug 区别）
followup_list_plans(patient_id) → 避免重复创建同类计划
```

### 2. 起草计划

计划应包含：

| 字段 | 说明 |
|------|------|
| `title` | 简洁计划名，如「高血压 2 周复查」 |
| `description` | 随访目的、注意事项 |
| `tasks` | 任务列表，每项含 `title`、`description`、`scheduled_at`（ISO8601） |

任务编排建议：

- 近期复查：3–14 天内
- 慢病随访：1–3 个月
- 每项任务职责单一（检查、复诊、用药依从、宣教等）

### 3. HITL 确认（必须）

```
request_followup_confirm(patient_id, title, description, tasks)
```

医生在界面审阅后确认 / 拒绝 / 编辑。

### 4. 创建计划

```
followup_create_plan(...)
```

> `followup_create_plan` 配置了 `interrupt_on`，会再次触发审批，属预期行为。

### 5. 执行与触达

- `followup_pending_tasks`：查看待办
- `followup_execute_task`：执行并记录结果
- `notification_create`：向患者发送复查 / 用药提醒

## 输出给主 Agent 的摘要格式

```
已为患者 {name} 创建随访计划「{title}」，共 {n} 项任务。
最近任务：{task_title}（{scheduled_at}）
```

避免返回冗长原始 JSON。

## 安全边界

- **不得**在未获医生确认的情况下调用 `followup_create_plan`
- 任务时间须合理，不得编造患者联系方式
- 敏感操作均需 HITL 通过

## 相关工具

| 工具 | 用途 |
|------|------|
| `patient_get` | 患者信息 |
| `followup_list_plans` | 已有计划 |
| `request_followup_confirm` | 计划 HITL |
| `followup_create_plan` | 创建计划 |
| `followup_pending_tasks` | 待办任务 |
| `followup_execute_task` | 执行任务 |
| `notification_create` | 患者提醒 |
