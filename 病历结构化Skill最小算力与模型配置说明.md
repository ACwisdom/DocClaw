# 病历结构化 Skill 最小算力与模型配置说明

> **文档用途**：基于 DocClaw 当前代码实现与项目文档，明确「门诊病历结构化」Skill 在**尚无多源 RAG / 知识库**阶段，为保证输出质量与系统流畅运行所需的**最小模型参数规模**与**最小算力配置**。  
> **适用版本**：DocClaw MVP（Skill Runtime 短路通路，2026-06）  
> **关联文档**：[`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) 第 7 节、[`README.md`](./README.md)、[`HARNESS_PLAN.md`](./HARNESS_PLAN.md)

---

## 1. 执行摘要（直接结论）

| 维度 | 最小可用（PoC / 内测） | **推荐下限（质量合格 + 流畅）** | 生产级 |
|------|------------------------|----------------------------------|--------|
| **模型参数** | **14B** 指令模型 + 严格 JSON Schema + 医生必审 | **32B** 指令模型（INT4）或同等 API（GPT-4o / Claude Sonnet 级） | 70B+ 或 Claude Opus / GPT-4.1 |
| **自建 GPU** | RTX 3060 12GB（14B INT4，1 路） | **RTX 4090 24GB 或 A10 24GB × 1** | A100 40GB+ / 多卡 |
| **API 方案** | GPT-4o-mini / Qwen-Plus | **GPT-4o / Claude 3.5 Sonnet** | Claude Opus / GPT-4.1 |
| **应用机（无 GPU）** | 2 核 4GB | **4 核 8GB**（跑 DocClaw 四服务） | 8 核 16GB+ |
| **并发（病历 Skill）** | 1 路 | **1 路为主，峰值 ≤ 3 路**（单卡 32B） | 10–30 路（科室八卡） |
| **端到端延迟目标** | P95 ≤ 15s | **P95 ≤ 8s（本地 32B）/ ≤ 3s（API）** | P95 ≤ 5s |

**一句话结论**：

> 在当前**无 RAG** 阶段，要保证结构化病历「质量合格、医生可用、系统不卡」，**模型下限为 32B（或 GPT-4o / Claude Sonnet 同级 API）**；**自建算力下限为单卡 RTX 4090 / A10 24GB（32B INT4）+ 应用机 4C8G**。14B 仅适合 PoC 与简单病例；**7B 及以下不建议用于临床辅助**。

---

## 2. 任务定义：当前 Skill 实际在做什么

### 2.1 执行路径（通路 A）

DocClaw 问诊页 **Skill 模式** + 默认「智能病历助手」+ 病历意图（如「帮我输出病历」）时，走 **Skill Runtime 短路**，**不经过 LangGraph 多步编排**：

```
医生触发病历意图
  → skill_runtime / skill_runtime_stream
  → run_medical_record_skill（单次 LLM 调用）
  → JSON Schema 校验（Pydantic OutpatientMedicalRecord）
  → field_diff 事实一致性比对
  → SSE 推送 structured 事件 + Markdown 展示
  → 医生审核确认（HITL）
```

核心代码位置：

- Schema：`backend/app/medical_record/schema.py`（10 个结构化字段 + missing_fields + confidence_notes）
- Prompt：`backend/app/medical_record/prompts.py`（嵌入 JSON Schema，禁止编造）
- 执行：`backend/app/medical_record/service.py`（`response_format: json_object`，失败降级 mock）

### 2.2 与 Agent 模式（通路 B）的区别

| 项目 | Skill 模式（病历结构化） | Agent 模式 |
|------|--------------------------|------------|
| 触发 | 病历意图关键词 | 自然语言 + 子 Agent 编排 |
| LLM 调用次数 | **1 次** | 多轮（工具调用 + 子 Agent） |
| 输出约束 | **强制 JSON Schema** | 自由文本 + HITL |
| 算力特征 | 单次大上下文、结构化输出 | 多轮小请求、延迟累加 |
| 质量关键 | **模型推理能力 + Schema** | 模型 + 工具链 + 记忆 |

本文档聚焦 **Skill 模式下的病历结构化**；Agent 模式额外消耗算力，若双轨同时启用，需在应用层做并发隔离（见第 6 节）。

### 2.3 当前缺失的能力（影响质量上限）

根据 `PROJECT_CONTEXT.md` 与代码现状：

| 能力 | 状态 | 对算力/质量的影响 |
|------|------|-------------------|
| 多源 RAG / 科室规范库 | ❌ 未接入 | 上下文更短（算力压力小），但**术语规范与专科模板靠模型自身能力** |
| 真实 HIS 深度对接 | ❌ Mock | 无额外 HIS 查询 Token，但既往史/检验数据不完整 |
| 本地 32B 部署 | ❌ 未部署 | 当前默认 `gpt-4o-mini` API 过渡 |
| 质量评测集 | ❌ 未建 | 需人工抽检验收 |

**无 RAG 的双面性**：

- **算力侧**：单次请求约 **3K–8K tokens**，无向量检索与 Embedding 开销，对 GPU 更友好。
- **质量侧**：缺少科室模板与指南注入，**同等参数规模下质量上限低于「有 RAG」方案**，因此模型规模下限不能低于 32B（或同级 API）。

---

## 3. 「质量合格」的判定标准

与 `PROJECT_CONTEXT.md` §7.1 对齐，结构化病历 Skill 输出视为合格需满足：

| 维度 | 指标 |
|------|------|
| 字段完整率 | 必填字段（主诉、现病史、查体、诊断、处理等）≥ 95% 有内容或明确「待补充」 |
| 事实一致性 | 不编造未在对话/患者上下文中出现的检查、用药、体征 |
| 术语规范 | 符合中文门诊病历书写习惯 |
| 时序逻辑 | 起病时间、病程描述合理 |
| 可用性（PoC） | 医生改稿时间较纯手工减少 ≥ 30% |
| 系统校验 | Pydantic 校验通过 + field_diff 无 critical conflict |

PoC 验收量化指标：

- 必填字段完整率 ≥ 90%
- 事实性错误率 ≤ 5%（人工抽检 100 份）
- JSON 解析成功率 ≥ 95%（Schema 合规）

---

## 4. 模型参数规模：分级建议

### 4.1 按参数规模

| 级别 | 模型规模 | 典型代表 | 结构化病历质量预期 | 是否建议用于 DocClaw 病历 Skill |
|------|----------|----------|-------------------|--------------------------------|
| 演示 | 7B | Qwen2.5-7B、Llama3.1-8B | 能出 JSON 形，**幻觉与漏项多** | ❌ 仅 Demo，不可临床辅助 |
| PoC 下限 | **14B** | Qwen2.5-14B-Instruct | 简单病例可用，复杂病例需大改 | △ 内测 + 人工必审 |
| **推荐下限** | **32B** | Qwen2.5-32B-Instruct、DeepSeek-V2.5-32B | **可作正式辅助草稿** | ✅ 个人版单卡目标 |
| 生产推荐 | 70B+ | Qwen2.5-72B、Llama3.1-70B | 多科室、长对话质量稳定 | ✅ 科室版 / 医院级 |

### 4.2 按 API 方案（多数团队 MVP 更现实）

| 方案 | 模型 | 质量预期 | 适用阶段 |
|------|------|----------|----------|
| 最低可用 | GPT-4o-mini、Qwen-Plus、DeepSeek-Chat | 简单病例够用，复杂病例幻觉风险 | PoC / 开发联调 |
| **推荐下限** | **GPT-4o、Claude 3.5 Sonnet** | 专科门诊草稿质量稳定 | **试点首选** |
| 高质量 | Claude Opus、GPT-4.1 | 复杂病例、长对话 | 生产 |

当前代码默认配置（`backend/app/config.py`）：

```python
llm_model: str = "gpt-4o-mini"   # 开发默认，质量未达「合格下限」
llm_temperature: float = 0.3     # 结构化任务已偏低，合理
llm_max_tokens: int = 2048       # 覆盖 ~800–1200 字 JSON 输出足够
```

**上线试点前应将 `LLM_MODEL` 提升至 GPT-4o / Claude Sonnet 级**，或在本地部署 32B。

### 4.3 无 RAG 时对模型规模的补偿

知识层缺失时，模型需独立承担：

- 医学术语规范化
- 现病史时序归纳
- 「待补充」与「推断」的边界判断

经验法则：**无 RAG 时，模型规模要求比「有 RAG + 科室模板」高约一档**——即 PoC 用 14B 时，有 RAG 后可能可维持；无 RAG 时 PoC 下限应视为 **32B**，14B 仅作技术验证。

---

## 5. 单次请求的 Token 与数据量预算

### 5.1 Token 组成（无 RAG 阶段）

| 组成部分 | Token 量 | 说明 |
|----------|----------|------|
| System Prompt + JSON Schema | 800–1,500 | 含完整 Pydantic Schema 嵌入 |
| 患者上下文 | 200–500 | 姓名、主诉、检查摘要等 |
| 问诊对话（最近 20 轮） | 1,500–4,000 | `summarize_conversation` 截断 20 轮 |
| 输出结构化 JSON | 500–1,200 | 10 字段 + missing_fields + notes |
| **合计** | **约 3,000–8,000 tokens/次** | 预填充（Prefill）为主 |

### 5.2 引入 RAG 后的增量（预留）

| 增量项 | 额外 Token | 额外算力 |
|--------|-------------|----------|
| 科室规范 / 模板检索 Top-3 | +500–1,500 | Embedding 模型 + 向量库 |
| 指南片段 Top-5 | +800–2,000 | 检索延迟 +50–200ms |
| 多源患者文档摘要 | +1,000–3,000 | 文档解析 CPU |

**当前无 RAG**：无需为检索预留 GPU；**未来接入 RAG 后**，建议在应用机增加 **2–4GB 内存**（Embedding 服务）或在 GPU 上预留 **2–4GB 显存**（若 Embedding 与 LLM 同机）。

### 5.3 单医生日 Token 量

- 触发频率：诊中每 2–3 分钟整理一次
- 估算：**50,000–150,000 tokens/天/医生**
- API 成本：按 GPT-4o 计价约 ¥1–5/天/医生（视触发频率）

---

## 6. 算力配置：自建 vs API

### 6.1 自建推理（国产算力 / 场算力一体机方向）

与 `PROJECT_CONTEXT.md` §7.3、§7.6 及 `temp_doc_extract.txt` 中国产场算力定位对齐。

#### 6.1.1 GPU 推理节点（LLM 专用）

| 模型 | 量化 | 最低 GPU | **推荐 GPU** | 显存占用 | 首 Token 延迟 | 生成速度（INT4） |
|------|------|----------|--------------|----------|---------------|------------------|
| 14B | INT4 | RTX 3060 12GB | RTX 4090 24GB | 10–12 GB | 1–3 s | 25–40 tok/s |
| **32B** | INT4 | RTX 4090 24GB | A10 24GB / L40 | 20–24 GB | 2–5 s | 15–30 tok/s |
| 70B | INT4 | 2×4090 / A100 40GB | A100 80GB | 40 GB+ | 3–8 s | 10–20 tok/s |

**病历 Skill 推荐下限配置（单医生个人版）**：

| 组件 | 规格 |
|------|------|
| GPU | **NVIDIA RTX 4090 24GB 或 A10 24GB × 1** |
| 模型 | **Qwen2.5-32B-Instruct INT4**（或沐曦生态等价 32B 指令模型） |
| 推理框架 | vLLM / llama.cpp / TensorRT-LLM（需支持 JSON mode 或 guided decoding） |
| 显存 | 20–24 GB（留 1–2 GB 给 KV Cache 并发） |

#### 6.1.2 应用节点（DocClaw 四服务，与 GPU 分离部署为佳）

DocClaw 同时运行：

| 服务 | 端口 | 资源特征 |
|------|------|----------|
| Medical API | 8000 | FastAPI + SQLite，轻量 |
| MCP Server | 8001 | 工具层，轻量 |
| Agent API | 8090 | LangGraph + DeepAgents，**内存占用较高** |
| Frontend | 5173 | Vite 开发服 / Nginx 静态 |

**应用机最小规格（无 GPU，API 或远程推理）**：

| 资源 | PoC | **推荐（流畅）** |
|------|-----|------------------|
| CPU | 2 核 | **4 核** |
| 内存 | 4 GB | **8 GB**（Agent Harness 建议 8 GB+） |
| 磁盘 | 20 GB | **50 GB+**（含模型缓存、日志、SQLite） |
| 网络 | 10 Mbps | **50 Mbps+**（API 方案或远程推理） |

**一体机合并部署（GPU + 应用同机）**：

| 资源 | 规格 |
|------|------|
| CPU | **8 核+** |
| 内存 | **32 GB+**（32B 推理不占用系统内存，但 Agent / OS 需要） |
| GPU | RTX 4090 / A10 24GB × 1 |
| 磁盘 | 100 GB SSD |

> CPU 纯推理 7B（5–15 tok/s）**不适合**门诊实时结构化；若仅有 CPU，应走 API 方案。

### 6.2 API 方案（当前代码默认路径）

| 项目 | 规格 |
|------|------|
| GPU | **无需** |
| 应用机 | 2C4G（PoC）/ **4C8G（推荐）** |
| 模型 | GPT-4o / Claude Sonnet（质量下限） |
| 延迟 | P95 **< 3 s**（含网络） |
| 并发 | 受 API 配额限制，单医生无压力 |

配置示例（`backend/.env`）：

```env
LLM_PROVIDER=openai_compat
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2048
LLM_FALLBACK_TO_MOCK=false   # 生产环境应关闭 mock 降级
```

---

## 7. 并发、实时性与「不卡顿」设计

### 7.1 业务并发模型（无 RAG 阶段）

| 场景 | 并发特征 | 算力需求 |
|------|----------|----------|
| 单医生个人版 | 1 路问诊 + 每 2–3 分钟 1 次病历结构化 | 1 路 LLM 为主 |
| 峰值 | 问诊对话流式 + 同时触发病历整理 | **≤ 2 路 LLM** |
| 科室版（未来） | 10–30 医生同时看诊 | 10–30 路，需多卡或推理集群 |

### 7.2 单卡 32B INT4 并发上限

| 并发路数 | 体验 | 建议 |
|----------|------|------|
| 1 路 | 流畅，首 Token 2–5 s，整份病历 5–10 s | ✅ 默认 |
| 2–3 路 | 可接受，延迟线性增加 | ✅ 个人版峰值上限 |
| 4+ 路 | KV Cache 争抢，明显卡顿 | ❌ 需排队或加卡 |

**推荐治理策略**：

1. **请求队列**：病历 Skill 为 `REALTIME` 任务，优先级高于随访等计划任务
2. **并发限制**：单卡 32B 设置 `max_concurrent=3`，超出返回「系统繁忙，请稍后」
3. **Skill 与 Agent 隔离**：Agent 模式（8090）使用独立 API Key 或独立推理实例，避免与 Skill 抢同一张卡
4. **超时**：当前 `llm_timeout=60s`；生产建议 **30s** 超时 + 友好降级提示

### 7.3 实时性 SLA（Skill 模式）

| 指标 | 14B 本地 | 32B 本地 | API（GPT-4o） |
|------|----------|----------|---------------|
| 首 Token | 1–3 s | 2–5 s | 0.5–1.5 s |
| 完整 JSON 输出 | 3–8 s | **5–12 s** | **2–5 s** |
| P95 端到端 | ≤ 10 s | **≤ 15 s** | **≤ 3 s** |
| 用户感知 | 需 Loading 态 | 需 Loading 态 + 进度文案 | 接近实时 |

病历 Skill 当前为**非流式一次性返回 JSON**（`run_medical_record_skill` 阻塞等待），前端已展示「正在生成结构化病历...」状态。为保证不卡顿：

- P95 ≤ 15 s 内必须有结果或明确错误
- 超过 10 s 应显示「生成中，请稍候」避免重复点击
- 禁止在 LLM 推理期间阻塞 UI 主线程（当前 SSE 架构已满足）

### 7.4 SQLite 与数据量

当前 MVP 使用 SQLite，单医生日问诊量 < 100 人时**不是瓶颈**。科室版（>10 医生、>1000 患者/天）需迁移 PostgreSQL，与 LLM 算力无关。

---

## 8. 质量保障机制（与算力同等重要）

模型与算力之外，DocClaw 已实现的质量护栏：

| 机制 | 实现 | 作用 |
|------|------|------|
| JSON Schema 强制 | Pydantic `OutpatientMedicalRecord` | 字段类型与结构 |
| 「待补充」策略 | Prompt + Validator | 抑制编造 |
| field_diff | `backend/app/medical_record/diff.py` | 标记 inferred / conflict |
| 身份校正 | `apply_patient_identity` | 姓名/性别/年龄以档案为准 |
| 失败降级 | JSON 解析失败 → mock 模板 + 警告 | 不静默出错 |
| HITL | 医生审核后写入 | 最后一道人工关 |

**算力再强也不能替代 HITL**；生产环境必须保留医生确认环节。

---

## 9. 分场景推荐配置清单

### 9.1 场景 A：个人开发者 / PoC 演示（可接受质量妥协）

| 项 | 配置 |
|----|------|
| 模型 | 14B INT4 或 GPT-4o-mini API |
| 算力 | RTX 3060 12GB **或** 2C4G 云主机 + API |
| 并发 | 1 路 |
| 质量预期 | 简单病例可用，复杂病例需大改；**不可作为临床辅助** |
| 必做 | 医生必审、关闭 mock 降级、建立 20 份评测集 |

### 9.2 场景 B：单医生试点（**推荐下限，质量合格 + 流畅**）

| 项 | 配置 |
|----|------|
| 模型 | **32B INT4（Qwen2.5-32B-Instruct）** 或 **GPT-4o / Claude Sonnet API** |
| 算力（自建） | **4090/A10 24GB × 1 + 应用机 4C8G** |
| 算力（API） | 4C8G 云主机，无 GPU |
| 并发 | 1 路为主，峰值 ≤ 3 路 |
| 延迟 | P95 ≤ 15 s（本地）/ ≤ 3 s（API） |
| 质量预期 | 专科门诊草稿可用，改稿时间减少 ≥ 30% |

### 9.3 场景 C：科室版（八卡，未来 Phase 2）

| 项 | 配置 |
|----|------|
| 模型 | 32B–70B 或多模型路由 |
| 算力 | **8 × A10/L40** 或等价国产八卡一体机 |
| 并发 | 10–30 路 |
| 附加 | RAG 知识层、MongoDB、PostgreSQL、请求队列 |

---

## 10. 未来引入 RAG 后的算力调整预告

| 变更 | 影响 |
|------|------|
| Embedding 模型（bge-m3 等） | 应用机 +2 GB 内存，或 GPU +2 GB 显存 |
| 向量库（Milvus / Qdrant） | 独立 2C4G 节点或容器 |
| 检索 Token 增量 | 单次 +1,500–3,500 tokens，Prefill 时间 +20–40% |
| 质量变化 | 14B + RAG 可能接近当前 32B 无 RAG；**仍建议 32B 为下限** |

RAG 接入后总延迟预算建议：**P95 ≤ 20 s（本地 32B）/ ≤ 5 s（API）**。

---

## 11. 验收检查表

部署前可按以下清单自检：

- [ ] `LLM_MODEL` 已设为 32B 本地或 GPT-4o / Claude Sonnet 级 API
- [ ] `LLM_FALLBACK_TO_MOCK=false`（生产）
- [ ] 单次病历请求 Token 监控：输入 3K–8K，输出 500–1,200
- [ ] P95 延迟：本地 ≤ 15 s，API ≤ 3 s
- [ ] 单卡并发 ≤ 3 路，超出有队列或拒绝策略
- [ ] 100 份抽检：字段完整率 ≥ 90%，事实错误率 ≤ 5%
- [ ] JSON 解析成功率 ≥ 95%
- [ ] Agent 模式与 Skill 模式推理资源已隔离（若双轨同机）
- [ ] 前端 Loading 态在 10 s 内不允许多次重复提交

---

## 12. 参考依据

| 来源 | 内容 |
|------|------|
| `PROJECT_CONTEXT.md` §7 | 算力与模型原始建议、PoC 指标 |
| `PROJECT_CONTEXT.md` §4.5 | 当前无 RAG / 无本地 32B 限制 |
| `backend/app/medical_record/` | Schema、Prompt、单次 LLM 调用实现 |
| `backend/app/config.py` | 默认 LLM 配置 |
| `temp_doc_extract.txt` | 国产场算力一体机产品定位 |
| `HARNESS_PLAN.md` Phase 6 | RAG / 算力路由待办 |

---

**文档版本**：v1.0  
**编写日期**：2026-06-07  
**维护建议**：本地 32B 部署或 RAG 接入后，更新第 5、6、10 节实测数据。
