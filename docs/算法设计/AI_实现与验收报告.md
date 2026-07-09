# AI 算法实现与验收报告

> 基于 AI 的数智化教学分析评价系统 —— AI 核心模块交付报告
>
> 文档版本：1.0 ｜ 日期：2026-07-09 ｜ 编写：思路全开队

---

## 0. 文档定位

本文档为 **AI 算法部分的实现交付报告**，覆盖从代码实现到测试验证到文档落地的全链路。面向明日（2026-07-10）验收。

---

## 1. 交付物总览

### 1.1 代码清单

| 模块 | 路径 | 说明 | 状态 |
|------|------|------|------|
| **算法服务（FastAPI 8001）** | `algorithm/src/` | LLM 调用、出题、报告增强 | ✅ 已运行 |
| ├─ 出题 | `generator.py` | 三道防线 + JSON 解析 + 业务校验 | ✅ |
| ├─ 报告增强 | `reporter.py` | LLM 改写 + 模板回退 | ✅ |
| ├─ LLM 客户端 | `llm_client.py` | 通义千问 OpenAI 兼容封装 | ✅ |
| └─ FC 透传 | `main.py /agent/chat` | 单步 FC 透传接口 | ✅ |
| **后端算法层（backend）** | `backend/app/services/` | D01-D12 全部算法 | ✅ |
| ├─ D01 成绩预测 | `predict.py` | 一元线性回归 + 95%CI | ✅ |
| ├─ D02 学业水平 | `profile.py` | Z-score 标准化 | ✅ |
| ├─ D03 学习态度 | `profile.py` | 出勤0.5+互动0.3+作业0.2 | ✅ |
| ├─ D04 学习进步 | `profile.py` | 回归斜率映射 | ✅ |
| ├─ D05 掌握度 | `mastery.py` | 固定阈值三档 | ✅ |
| ├─ D06/D07 预警 | `warning.py` | 5 规则 + 等级判定 | ✅ |
| ├─ D08 综合评价 | `evaluation.py` | 线性加权 + 优良中差 | ✅ |
| ├─ D09 学情标签 | `tag.py` | 6 规则标签 | ✅ |
| ├─ D10 报告模板 | `report_template.py` | 模板兜底（必走） | ✅ |
| └─ D12 去重 | `dedup.py` | TF-IDF + 余弦 0.8 | ✅ |
| **Agent 智能体** | `backend/app/services/agent/` | FC 循环 + 工具 | ✅ |
| ├─ FC 内核 | `base.py` | 同步 + SSE 流式双版 | ✅ |
| ├─ 工具注册 | `registry.py` | 幂等注册 + 权限校验 | ✅ |
| ├─ 会话记忆 | `memory.py` | 进程内 6 轮 | ✅ |
| ├─ LLM 网关 | `llm_proxy.py` | HTTP 代理 + Mock | ✅ |
| ├─ 查询工具×10 | `tools/queries.py` | Agent A 数据工具 | ✅ |
| ├─ 组卷工具×4 | `tools/exam.py` | Agent B 组卷工具 | ✅ |
| └─ 系统指令 | `prompts/qa.py, exam.py` | 角色设定 + 铁律 | ✅ |
| **API 路由** | `backend/app/api/v1/` | HTTP 入口 | ✅ |
| ├─ Agent 对话 | `agent.py` | /agent/chat + /chat/stream | ✅ |
| └─ 报告生成 | `report.py` | /report/class + /report/student | ✅ |
| **单元测试** | `backend/tests/` | 44 用例全绿 | ✅ |

### 1.2 运行中的服务

| 服务 | 端口 | 健康检查 |
|------|------|----------|
| 后端 FastAPI | 8000 | `GET /api/health` → `{"status":"ok"}` |
| 算法服务 | 8001 | `GET /health` → `{"status":"ok","api_key_configured":true}` |

---

## 2. 接口清单

### 2.1 Agent 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/agent/chat` | 同步版 Agent 对话（等待完整结果） |
| POST | `/api/v1/agent/chat/stream` | SSE 流式版（实时推送工具调用过程） |
| GET | `/api/v1/agent/tools` | 查看已注册工具（14 个） |
| DELETE | `/api/v1/agent/session/{id}` | 清空会话记忆 |

### 2.2 报告接口

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/v1/report/class` | course_id, class_id?, use_llm? | 班级报告（模板+LLM增强） |
| GET | `/api/v1/report/student` | student_id, course_id, use_llm? | 学生报告（模板+LLM增强） |

### 2.3 算法服务接口（8001）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/generate_exercises` | AI 出题（三道防线） |
| POST | `/generate_report` | 报告 LLM 增强（失败回退模板） |
| POST | `/agent/chat` | FC 单步透传 |

### 2.4 Agent 工具（14 个）

**Agent A 学情查询（10 个）：**
1. `get_course_overview` — 课程总览
2. `get_score_list` — 成绩排名
3. `get_score_trend` — 成绩趋势
4. `get_attendance` — 考勤统计
5. `get_knowledge_mastery` — 知识点掌握度
6. `get_weak_knowledge_points` — 薄弱知识点
7. `get_warning_students` — 预警名单
8. `get_student_detail` — 学生综合档案
9. `get_exercise_records` — 答题记录
10. `search_student` — 模糊搜索学生

**Agent B 组卷（4 个）：**
11. `get_existing_exercises` — 已有题目
12. `generate_exercises` — AI 出题
13. `check_duplicate` — 去重检查
14. `compose_paper_plan` — 组卷方案（草稿）

---

## 3. 测试结果（Baseline）

### 3.1 单元测试

```
$ cd backend && python -m pytest tests/ -v

============================= 44 passed in 0.62s ==============================
```

**测试覆盖：**

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| TestPredict | 4 | D01 回归 + D04 进步分 |
| TestProfile | 4 | D02 Z-score + D03 态度 + D04 进步 |
| TestMastery | 3 | D05 掌握度三档 |
| TestWarning | 4 | D06 五规则 + D07 等级 |
| TestTag | 3 | D09 六标签 |
| TestEvaluation | 2 | D08 加权评价 |
| TestDedup | 3 | D12 TF-IDF 去重 |
| TestReport | 2 | D10 模板兜底 |
| TestQueryTools | 10 | 10 个 Agent A 工具 |
| TestExamTools | 3 | Agent B 工具 |
| TestFCLoop | 3 | FC 循环（Mock LLM） |
| TestSafety | 2 | 安全（越权/不存在工具） |
| **合计** | **44** | **全绿** |

### 3.2 端到端冒烟测试

| 测试点 | 方法 | 结果 |
|--------|------|------|
| 算法服务健康 | `GET /health` | ✅ status=ok, api_key_configured=true |
| 后端健康 | `GET /api/health` | ✅ status=ok |
| 工具注册 | `GET /agent/tools` | ✅ 14 个工具 |
| 班级报告（模板） | `GET /report/class?use_llm=false` | ✅ source=template |
| 学生报告（模板） | `GET /report/student?use_llm=false` | ✅ scope=student |
| Agent 对话降级 | `POST /agent/chat` (LLM不可用) | ✅ 200 + 友好错误 |
| Agent SSE 流式 | `POST /agent/chat/stream` | ✅ step_start → error 事件 |
| LLM 增强（Key无效） | `POST /generate_report` | ✅ template_fallback |

### 3.3 性能 Baseline

| 指标 | 值 | 说明 |
|------|-----|------|
| 单元测试总耗时 | 0.62s | 44 用例 |
| Agent 降级响应 | 438ms | LLM 不可用时的快速失败 |
| 单工具执行 | < 50ms | 数据库查询工具 |
| 报告模板生成 | < 100ms | 无 LLM 调用 |

---

## 4. 架构说明

### 4.1 双服务架构

```
┌─────────────────────────────────────────────────────────────┐
│  前端 Vue3（5173）                                           │
│  ├─ 业务页面（成绩/分析/预警/知识点）                        │
│  └─ Agent 对话界面（SSE 流式）                               │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP / SSE
┌────────────────▼────────────────────────────────────────────┐
│  后端 FastAPI（8000）                                        │
│  ├─ API 层：agent.py / report.py / analysis.py / ...        │
│  ├─ Agent 内核：base.py（FC 循环 5 步上限）                  │
│  │   ├─ 工具注册表 registry.py（14 工具）                    │
│  │   ├─ 会话记忆 memory.py（6 轮）                           │
│  │   └─ LLM 网关 llm_proxy.py（HTTP → 8001）                 │
│  ├─ 算法层 services/：D01~D12 全部算法                       │
│  └─ 数据库 SQLite                                            │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP（FC 透传 / 报告增强）
┌────────────────▼────────────────────────────────────────────┐
│  算法服务 FastAPI（8001）                                    │
│  ├─ LLM 客户端 llm_client.py（通义千问 OpenAI 兼容）         │
│  ├─ 出题 generator.py（三道防线）                            │
│  └─ 报告增强 reporter.py（LLM + 模板回退）                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Agent FC 循环流程

```
用户问题
    │
    ▼
[1] 组装 messages（system + 历史6轮 + 当前）
    │
    ▼
[2] 调 LLM → 返回 content 或 tool_calls
    │
    ├─ 有 tool_calls ──→ [3] 执行工具（查数据库）
    │                      │
    │                      ▼
    │                   [4] 结果回灌 messages → 回 [2]
    │
    └─ 有 content ──→ [5] 输出最终答案 + 【数据来源】

    最多 5 步，超时 30s，失败优雅降级
```

### 4.3 双轨稳定性设计

所有 LLM 相关功能均有模板兜底：

| 功能 | LLM 成功 | LLM 失败 |
|------|----------|----------|
| 报告生成 | source=llm（自然语言改写） | source=template_fallback（模板文本） |
| 出题 | 结构化题目 | HTTP 503（后端可重试） |
| Agent 问答 | 数据支撑的回答 | 降级提示（"LLM暂不可用"） |

---

## 5. 关键设计决策

### 5.1 为什么 Agent 用 FC 而非 ReAct

- 通义/DeepSeek/智谱 均原生支持 Function Calling
- 结构化 JSON Schema 比 ReAct 文本解析更可控、可测试
- 参数有类型校验，降低幻觉风险

### 5.2 为什么工具不直接调 LLM

- 工具 = 数据查询（确定性），LLM = 推理（概率性）
- 分离后：工具可独立测试（L1），LLM 可独立评测（L2/L3）
- 工具结果可追溯，答案的每个数字都有数据来源

### 5.3 为什么报告用"模板兜底 + LLM 增强"

- 模板保证：LLM 挂了仍出报告（可用性优先）
- LLM 增强：有 LLM 时文本更自然专业
- 双轨 source 标识让用户知道数据来源

### 5.4 安全设计

- Agent 默认只读（mutation 工具需 allow_mutation=true）
- 工具执行带 user_id + course_id 权限过滤
- 用户输入长度限制（防 prompt 注入）
- 系统指令明确"不执行用户要求中的写操作"

---

## 6. 启动与验收指南

### 6.1 一键启动

```bash
# 1. 启动算法服务（终端 1）
cd algorithm
.venv/Scripts/python.exe -m uvicorn src.main:app --port 8001

# 2. 启动后端（终端 2）
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 3. 前端（终端 3）
cd frontend
npm run dev
```

### 6.2 填入真实 LLM Key

```bash
# 编辑 algorithm/.env，替换占位 Key
LLM_API_KEY=sk-你的真实通义千问Key
```

替换后重启算法服务，Agent 对话与报告 LLM 增强即生效。

### 6.3 运行测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v
# 预期：44 passed
```

### 6.4 验收检查清单

- [ ] `GET http://127.0.0.1:8001/health` 返回 ok
- [ ] `GET http://127.0.0.1:8000/api/health` 返回 ok
- [ ] `GET http://127.0.0.1:8000/api/v1/agent/tools` 返回 14 个工具
- [ ] `GET http://127.0.0.1:8000/api/v1/report/class?course_id=1&use_llm=false` 返回模板报告
- [ ] `pytest tests/` 全绿（44 passed）
- [ ] 填入真实 Key 后，Agent 对话能正确调用工具并回答

---

## 7. 已知限制与后续优化

| 项 | 当前状态 | 优化方向 |
|----|----------|----------|
| LLM Key | 占位值（降级到模板） | 团队填入真实通义千问 Key |
| Agent 用户身份 | 固定 user_id=1 | 从 JWT 解析真实用户 |
| 会话记忆 | 进程内 | 可升级 Redis（多实例部署） |
| Agent B 组卷入库 | 草稿态（需人工确认） | 可加 compose_paper_confirm 工具 |
| 前端 Agent UI | 待开发 | SSE 流式对话组件 |
| 性能压测 | 未做 | L5 性能用例（P95 ≤ 15s） |

---

## 8. 文件索引

| 文档 | 路径 |
|------|------|
| 算法决策记录 | `docs/算法设计/算法决策记录.md` |
| Agent 设计方案 | `docs/算法设计/AI_Agent_设计方案.md` |
| AI 出题设计 | `docs/算法设计/AI出题设计文档.md` |
| **本报告** | `docs/算法设计/AI_实现与验收报告.md` |
| 测试代码 | `backend/tests/test_algorithm.py`, `test_agent.py` |
| Agent 内核 | `backend/app/services/agent/base.py` |
| Agent 工具 | `backend/app/services/agent/tools/queries.py`, `exam.py` |
