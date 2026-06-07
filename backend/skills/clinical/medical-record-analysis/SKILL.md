---
name: medical-record-analysis
version: "1.0.0"
description: >
  临床病历分析与草稿生成 SOP。用于问诊数据汇总、检查结果解读、
  门诊病历结构化草稿（非最终写入）。须配合 request_record_confirm HITL。
tags: ["clinical", "medical-record", "analysis", "docclaw"]
---

# 病历分析与草稿生成

## 适用场景

- 医生要求分析当前问诊对话、检查与既往史
- 需要生成**门诊病历**供医生审阅（非 Skill 模式实时结构化）
- 解读 `his_get_labs` / `his_get_history` 返回的数据

**不适用**：诊中实时高质量 Schema 输出 → 提示医生切换 Skill 模式「智能病历助手」。

## 标准工作流

1. **采集数据**
   - `patient_get`：患者基本信息、主诉、已完成检查
   - `consult_get_messages`：本轮问诊对话
   - `his_get_labs` / `his_get_history`：检查与既往摘要

2. **分析与草稿**
   - 仅依据工具返回的真实数据，**不得编造**检查、诊断或用药
   - 未出现的信息对应字段填「待补充」
   - 输出结构化字段（与 DocClaw Schema 对齐）：
     - 主诉、现病史、既往史、过敏史
     - 查体、辅助检查、初步诊断、处理意见
     - `missing_fields`：仍为「待补充」的字段中文名列表
     - `confidence_notes`：需医生重点核实的内容

3. **HITL 确认（必须）**
   - 调用 `request_record_confirm(patient_slug, draft_content, structured_data)`
   - 等待医生在界面确认 / 拒绝 / 编辑
   - 确认后方可由流程写入正式病历（`his_write_record`）

## 输出原则

1. 只依据患者上下文与问诊对话生成内容
2. 未在对话或患者上下文中出现的检查、用药、体征、诊断 → 填「待补充」
3. `missing_fields` 列出仍为「待补充」的字段中文名
4. `confidence_notes` 写明需医生重点核实的内容；无则留空

## 安全边界

- 不得跳过 `request_record_confirm` 直接写入正式病历
- 不得虚构检查结果或诊断结论
- 草稿仅供医生审阅，不代表最终医疗记录

## 相关工具

| 工具 | 用途 |
|------|------|
| `patient_get` | 患者档案 |
| `consult_get_messages` | 问诊历史 |
| `his_get_labs` | 已完成检查 |
| `his_get_history` | 既往史摘要 |
| `request_record_confirm` | 病历 HITL |
| `web_search` | 文献/指南检索（辅助解读） |
