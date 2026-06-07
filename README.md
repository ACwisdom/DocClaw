# DocClaw · 医疗 AI 工作台

DocClaw（目标产品名 **DoctorClaw**）是一个面向医生的医疗 Skills 管理平台：医生可启用、自定义、发布 AI 技能，在问诊过程中获得实时辅助，并管理随访等计划性任务。

> 代码仓库为 **DocClaw** MVP；终局愿景为基于国产算力的 **DoctorClaw 医疗智能体平台**（Skills 引擎 + 患者连续管理 + 科室 SkillsHub）。

---

## 核心能力

| 模块 | 说明 |
|------|------|
| **患者队列** | 今日问诊列表，支持状态 / 类型筛选 |
| **问诊工作台** | Skill 模式 + Agent 模式双轨；门诊病历结构化、检查结果分析 |
| **个人技能** | 管理本地 AI 技能，启用 / 停用 / 发布 |
| **技能广场** | 浏览、获取其他医生分享的技能及 [ClawHub](https://clawhub.ai/) 开放技能 |
| **随访计划** | 创建随访计划，APScheduler 自动 / 手动执行 |
| **通知中心** | 任务提醒与系统通知 |

### 病历结构化（核心 Skill）

问诊页 **Skill 模式** 下，触发「帮我输出病历」等意图时，走 **Skill Runtime 短路**：

```
问诊对话 + 患者上下文
  → 单次 LLM 调用（JSON Schema）
  → Pydantic 校验 + field_diff 事实比对
  → SSE 推送结构化结果
  → 医生 HITL 确认
```

**质量合格下限**（当前无 RAG 阶段）：**32B 模型（或 GPT-4o / Claude Sonnet 级 API）+ 单卡 RTX 4090 / A10 24GB**；详见 [`病历结构化Skill最小算力与模型配置说明.md`](./病历结构化Skill最小算力与模型配置说明.md)（[Word 版](./病历结构化Skill最小算力与模型配置说明.docx)）。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React · TypeScript · Vite · React Router |
| 业务 API | FastAPI · SQLAlchemy · SQLite · APScheduler |
| AI / Skill | OpenAI 兼容 LLM · Pydantic Structured Output · SSE 流式 |
| Agent Harness | DeepAgents · LangGraph · MCP · HITL |

---

## 架构概览

问诊工作台支持两条 AI 通路：

| 通路 | 触发 | 执行路径 |
|------|------|----------|
| **A. Skill Runtime** | Skill 模式 + 病历意图 | 单次 Structured Output，Schema 质量优先 |
| **B. DeepAgents Harness** | Agent 模式 | 主 Agent → 子 Agent → MCP 工具 → HITL |

### 服务与端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Medical API | 8000 | 患者、问诊、技能、随访等业务 |
| MCP Server | 8001 | Agent 工具层 |
| Agent API | 8090 | SSE 对话 + HITL `/resume` |
| Frontend | 5173 | 医生工作台 UI |

---

## 快速启动

### 环境要求

- Python 3.11+（Harness 依赖）
- Node.js 18+
- （可选）MongoDB — HITL 跨请求续跑
- （可选）`LLM_API_KEY` — 未配置时使用 mock 降级

### 一键启动（Windows）

```bat
start.bat
```

### 手动启动

```bash
# 1. 业务后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2. 前端
cd frontend
npm install
npm run dev

# 3. Agent Harness（可选）
cd backend
pip install -r requirements-agent.txt
py -3.11 start_agent.py
```

访问 **http://localhost:5173**

### LLM 配置

在 `backend/.env` 中配置：

```env
LLM_PROVIDER=openai_compat
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2048
LLM_FALLBACK_TO_MOCK=false
```

---

## 页面路由

| 路由 | 说明 |
|------|------|
| `/queue` | 患者队列 |
| `/skills` | 个人技能 |
| `/skills/new` | 创建技能 |
| `/store` | 技能广场 |
| `/consult/:slug` | 问诊工作台 |
| `/followup` | 随访计划 |
| `/notifications` | 通知中心 |

API 文档：启动后端后访问 http://localhost:8000/docs

---

## 项目结构

```
DocClaw/
├── README.md                              # 本文件
├── PROJECT_CONTEXT.md                     # 项目全景上下文（新对话必读）
├── HARNESS_PLAN.md                        # DeepAgents 分期实施计划
├── DEMO.md                                # 演示与验收步骤
├── 病历结构化Skill最小算力与模型配置说明.md  # 算力 / 模型配置说明
├── start.bat                              # Windows 一键启动
├── run_acceptance.bat                     # Phase 5 验收入口
├── frontend/                              # React 前端
├── backend/
│   ├── app/                               # 业务 API（:8000）
│   │   ├── medical_record/                # 病历 Schema、Prompt、校验
│   │   ├── services/skill_runtime*.py     # Skill 执行与流式
│   │   └── services/llm/                  # OpenAI 兼容 + mock 降级
│   ├── agent/                             # DeepAgents Harness（:8090）
│   ├── skills/                            # 技能手册（clinical / clawhub）
│   └── scripts/                           # 验收、ClawHub 同步等脚本
└── scripts/
    └── md_to_docx.py                      # Markdown → Word 转换工具
```

---

## 文档索引

| 文档 | 用途 |
|------|------|
| [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) | 目标蓝图、架构缺口、分阶段 Plan、API 清单 |
| [`HARNESS_PLAN.md`](./HARNESS_PLAN.md) | DeepAgents Harness Phase 0–6 实施详表 |
| [`DEMO.md`](./DEMO.md) | 6 步演示闭环与验收 |
| [`病历结构化Skill最小算力与模型配置说明.md`](./病历结构化Skill最小算力与模型配置说明.md) | 病历 Skill 最小算力与模型参数 |
| [`录屏演示指南.md`](./录屏演示指南.md) | 录屏演示操作指引 |

---

## 验收与演示

```bat
run_acceptance.bat
```

或：

```bash
cd backend
python scripts/e2e_acceptance.py
python scripts/e2e_acceptance.py --with-llm --with-agent
```

详见 [`DEMO.md`](./DEMO.md)。

---

## ClawHub 技能同步

启动后端时自动从 ClawHub 拉取医疗相关开放技能（幂等）。手动同步：

```bash
cd backend
python scripts/import_clawhub_skills.py
python scripts/import_clawhub_skills.py --slug pubmed-search-skill
```

或在技能广场点击「同步 ClawHub」，或调用 `POST /api/store/sync-clawhub`。

---

## 当前限制（MVP）

- 无登录 / 多租户，固定「李医生」演示账号
- HIS 为 Mock，无真实 EMR 写入
- 知识层 / RAG 未接入
- 本地 32B 模型未部署，默认 API 过渡
- MongoDB 未部署时 HITL 跨刷新续跑不稳定

---

## 相关链接

- ClawHub 技能市场：https://clawhub.ai/

---

**最后更新**：2026-06-07
