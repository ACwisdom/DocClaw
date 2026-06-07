# DocClaw Phase 5 端到端演示指南

对应 `HARNESS_PLAN.md` 第 13 节 6 步验收。演示患者默认为 **`patient-zhang-san`（王浩然，26 岁）**。

## 启动环境

```bash
# 方式一：一键（Windows）
start.bat

# 方式二：手动四进程
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && py -3.11 start_agent.py          # MCP :8001 + Agent :8090
cd frontend && npm run dev                      # :5173

# 可选：MongoDB（HITL 跨请求续跑）
docker run -d -p 27017:27017 --name docclaw-mongo mongo:7
```

配置 `backend/.env`：

```env
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
DEEPSEEK_API_KEY=...    # Agent 用，可与 LLM_API_KEY 相同
MONGODB_URI=mongodb://localhost:27017
```

## 自动验收

```bash
cd backend

# 基础验收（无需 LLM，需 :8000）
py -3.11 scripts/e2e_acceptance.py

# 含 Skill 流式 + Agent 冒烟
py -3.11 scripts/e2e_acceptance.py --with-llm --with-agent
```

## 六步手动演示

### 步骤 1：待接诊统计

**Agent 模式**（问诊页切换 Agent，或 Swagger `POST :8090/api/agent/chat`）：

> 今天多少待接诊？

预期：主 Agent 调用 `patient_summary`，返回待接诊/问诊中/已完成数量。

### 步骤 2：患者详情与检查

> 王浩然的主诉和检查结果是什么？

预期：委派 `clinical-assistant`，调用 `patient_get` + `his_get_labs`。

### 步骤 3：Skill 模式病历结构化

1. 打开 http://localhost:5173/consult/patient-zhang-san
2. 保持 **Skill 模式**，选择「智能病历助手」
3. 发送：「请根据当前问诊整理门诊病历」

预期：SSE 返回 `structured` 事件，界面展示病历卡片与 `field_diffs`。

### 步骤 4：Agent 模式创建随访（HITL）

1. 切换到 **Agent 模式**
2. 发送：「给王浩然创建 2 周后复查的随访计划，包含复查提醒任务」
3. 出现 **InterruptBanner** 后点击「确认」
4. 打开 http://localhost:5173/followup?patient={id} 验证计划已落库

> 无 MongoDB 时 HITL 仅同进程有效；生产演示请启动 MongoDB。

### 步骤 5：调度器执行 → 通知

随访任务 `scheduled_at` 到期后，后台调度器（每分钟）自动执行并 **产生通知**。

手动加速验收：

```bash
cd backend
py -3.11 scripts/e2e_acceptance.py   # 步骤 5 自动创建到期任务并验证通知
```

预期：http://localhost:5173/notifications 出现「随访任务已执行」通知。

### 步骤 6：待办随访查询

**Agent 模式**发送：

> 有哪些待执行的随访任务？

预期：`followup-executor` 调用 `followup_pending_tasks` 返回列表。

## 能力对照（Phase 5 后）

| 能力 | 状态 |
|------|------|
| Skill 框架 | ✅ |
| MCP 医疗工具 | ✅ |
| DeepAgents 调度中枢 | ✅ |
| 患者管理 | ✅ |
| 实时 + 计划性任务 | ✅ |
| HITL 病历/随访 | ✅ |
| 工具调用审计 | ✅ `GET /api/audit/agent-tools` |
| RAG / 国产算力 / ASR | ⏳ Phase 6 |

## 常见问题

| 现象 | 处理 |
|------|------|
| Agent API 503 | 检查 `DEEPSEEK_API_KEY`，查看 :8090/health |
| HITL 续跑失败 | 启动 MongoDB，配置 `MONGODB_URI` |
| Skill 流式无结构化 | 确认默认技能启用，消息含「病历」关键词 |
| 通知未出现 | 确认 Medical API 运行中（调度器随 app 启动） |
