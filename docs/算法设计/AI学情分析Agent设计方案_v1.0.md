# AI 学情分析 Agent 设计方案 v1.0

> 状态:设计稿(2026-09-07)
> 模块:智能分析 > AI 学情分析
> 路由:`/analysis/diagnosis`(teacher)
> 定位:主动式 AI 综合学情诊断,自动编排多工具拉全量数据 → 输出结构化诊断报告(归因 + 干预建议),过程透明可追问、结果可导出可联动干预。

---

## 1. 功能定位与边界

### 1.1 与现有功能的差异

| 现有功能 | 形态 | 局限 |
|---|---|---|
| 学情画像 / 知识点掌握度 / 异常预警 | 数据可视化(雷达图/热力图/列表) | 只展示数据,不做归因与建议 |
| Agent 学情问答(`/agent/chat`,agent_type=qa) | 对话式,老师问什么答什么 | 被动,老师得知道该问什么 |
| 报告中心(`/report`) | 模板填空三段式 + PDF/Excel 导出 | 模板化,非 AI 综合推理 |

**本功能定位:主动式 AI 综合诊断。** 老师选班级或学生 → 点"开始 AI 分析" → AI 自动编排多个学情查询工具(总览/成绩/考勤/知识点/预警/答题)→ 输出结构化诊断报告(总体评估 + 关键发现 + 归因分析 + 干预建议),过程透明可见,结果可追问、可导出、可联动生成干预任务。

差异化:
- 比 Agent 问答**更主动**(不用老师想问什么)
- 比报告中心**更智能**(AI 综合推理而非模板填空)
- 比画像页**更深**(给归因和干预建议而不止于数据)

### 1.2 设计决策(已拍板)

| 决策点 | 选择 | 说明 |
|---|---|---|
| 分析对象范围 | **班级 + 学生都支持** | 复用 AnalysisFilterBar 的分析对象切换,与学情画像页一致;报告渲染做两套(班级共性问题 / 学生个人深度) |
| 交互形态 | **一键触发 + 过程可见 + 可追问** | 点一下开始 → SSE 实时展示工具调用过程(可折叠)→ 出报告后下方可追问(走 agent/chat 多轮) |
| 结果去向 | **导出报告 + 生成干预任务** | 诊断结果可导出 PDF/Excel(复用 report.py),并可一键跳转"薄弱点驱动出题"或对预警学生发通知,形成"诊断→干预"闭环 |

---

## 2. 页面设计

整体仿 `StudentProfileView` 的 `page-container` + `content-card` 蓝灰风格(主色 `#2563eb`,背景 `#f1f5f9`,文字 `#1e293b`/`#64748b`)。

### 2.1 班级诊断视角(分析对象 = 班级)

```
智能分析 > AI 学情分析
┌──────────────────────────────────────────────────────────────┐
│ [AnalysisFilterBar]                                           │
│ 学期▼  课程▼  班级▼   分析对象:(●)班级 ( )学生   [查询]      │
├──────────────────────────────────────────────────────────────┤
│ 分析维度  ☑成绩 ☑考勤 ☑知识点 ☑预警 ☐答题   深度:(●)详细( )概览│
│                                              [ 🤖 开始AI分析 ] │
└──────────────────────────────────────────────────────────────┘

┌── 过程区(分析中,SSE 流式实时渲染,仿 AgentChat 的 toolCalls)──┐
│ 🤔 AI 正在诊断…                                                │
│ ▸ step1  get_course_overview     ✓ 45人·均分72·及格率84%       │
│ ▸ step2  get_weak_knowledge_pts  ✓ 图论42%·最短路55%           │
│ ▸ step3  get_warning_students    ✓ 3人预警(1高2中)            │
│ ▸ step4  get_score_trend         ⠋ 进行中…                     │
│   [展开查看原始数据 ▾]                                          │
└──────────────────────────────────────────────────────────────┘

┌── 诊断报告区(完成后渲染)────────────────────────────────────┐
│ 📊 总体评估          综合评级 B(78/100)   [小雷达图]          │
│ ──────────────────────────────────────────────────────────── │
│ 🔍 关键发现                                                   │
│   ✅ 优势  课堂参与度 92%(年级前列)、出勤稳定 96%             │
│   ⚠️ 风险  3 名学生成绩持续下滑、知识点"图论"掌握度仅 42%     │
│ ──────────────────────────────────────────────────────────── │
│ 🧠 归因分析                                                   │
│   • "图论"薄弱:实验报告扣分集中在该模块(占失分 58%)         │
│   • 下滑学生:出勤率与作业提交率同步下降,疑似态度问题         │
│ ──────────────────────────────────────────────────────────── │
│ 💡 干预建议                                                   │
│   1. [高] 针对图论开展专项复习 → [薄弱点驱动出题]             │
│   2. [中] 对 3 名下滑学生约谈 → [查看名单/发通知]             │
│ ──────────────────────────────────────────────────────────── │
│ [💬 追问 AI…]  [📄 导出报告]  [📋 生成干预任务]               │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 学生诊断视角(分析对象 = 学生)

AnalysisFilterBar 切到"学生"并选具体学生后,过程区相同,报告区换成单生深度档案:

```
┌── 诊断报告区(学生视角)──────────────────────────────────────┐
│ 👤 张三  学号2021xxx  计科2101  综合评级 C(68/100)            │
│ ┌─雷达五轴─┐  ┌─历次成绩趋势─┐  ┌─学习态度构成─┐            │
│ │ 成绩65   │  │  /\__         │  │ 出勤82 互动70 │            │
│ │ 考勤82   │  │ /   \_  ↓预测 │  │ 作业60 综合68 │            │
│ │ 互动70   │  │       65      │  └───────────────┘            │
│ │ 进步58   │  └───────────────┘                                │
│ │ 综合68   │                                                   │
│ └──────────┘                                                   │
│ ──────────────────────────────────────────────────────────── │
│ 🔍 关键发现                                                   │
│   ⚠️ 成绩连续 3 次下滑(85→76→65)、图论掌握度 35%(班级垫底)   │
│   ✅ 课堂互动活跃(班级前 20%)                                │
│ ──────────────────────────────────────────────────────────── │
│ 🧠 归因分析                                                   │
│   • 图论模块失分占个人总失分 62%,是成绩下滑主因              │
│   • 作业提交率 60% 偏低,与下滑时点吻合,疑似学习态度松懈      │
│ ──────────────────────────────────────────────────────────── │
│ 💡 个性化建议                                                 │
│   1. [高] 图论补强:推荐 3 道薄弱点专项题 → [开始练习]         │
│   2. [中] 改善作业提交习惯,建议教师约谈                       │
│ ──────────────────────────────────────────────────────────── │
│ [💬 追问 AI…]  [📄 导出报告]  [📋 生成干预任务]               │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 空状态 / 加载态

- 未点"开始 AI 分析"时:报告区显示引导卡(`el-empty`)——"选择分析对象与维度,点击开始 AI 分析,系统将自动调用学情数据生成诊断报告",附 2-3 个快捷场景按钮("诊断班级薄弱点""分析某学生下滑原因")。
- 分析中:过程区显示工具调用进度,报告区显示骨架屏(`el-skeleton`)。
- 失败:过程区标红失败步骤,报告区显示"诊断失败,可重试",带 [重新分析] 按钮。

---

## 3. 交互流程

```
选 学期/课程/班级/(学生)
   │
   ├─ 勾维度 + 选深度 ──▶ 点[开始AI分析]
   │
   ▼
后端 run_agent_stream(agent_type="diagnosis")
   │  ← DIAGNOSIS_SYSTEM_PROMPT 指示 AI:
   │     1. 主动调用 5-6 个工具拉全量数据(按勾选维度)
   │     2. 综合分析后输出结构化 JSON 诊断报告
   │
   ├─ SSE: step_start / tool_call / tool_result  ──▶ 前端过程区实时渲染
   ├─ SSE: content (结构化 JSON 诊断报告)        ──▶ 前端报告区渲染
   └─ SSE: done
   │
   ▼
老师后续操作:
   • 追问    → 走 /agent/chat/stream(agent_type=qa,同 session_id)复用会话记忆
   • 导出    → 调 report.py 的 PDF/Excel(把诊断结果塞进 ReportContext)
   • 干预    → 跳转 AI 出题(薄弱点驱动)/ 对预警学生发通知
```

**追问设计:** 诊断完成后,报告区底部 `[💬 追问 AI…]` 展开输入框。追问复用现有 `agent_type=qa` 学情问答(同 session_id 继承诊断上下文),不新建 agent_type。这样诊断是"一次性深度分析",追问是"基于诊断的轻量对话",职责清晰。

---

## 4. 技术架构

### 4.1 复用(已有能力直接拿来用)

| 能力 | 文件 | 复用方式 |
|---|---|---|
| 10 个学情查询工具 | `backend/app/services/agent/tools/queries.py` | 覆盖全部数据获取(总览/成绩/趋势/考勤/知识点/薄弱点/预警/学生档案/答题/搜索),无需新建工具 |
| Agent FC 循环 | `backend/app/services/agent/base.py:run_agent_stream` | 直接驱动诊断,最多 5 步工具调用 |
| SSE 流式消费 | `frontend/src/api/agent.ts:streamAgentChat` | 前端过程渲染,事件映射 step_start/tool_call/tool_result/content/done |
| LLM 网关 | `backend/app/services/agent/llm_proxy.py` | HTTP 调 8001 algorithm 服务,复用 DeepSeek |
| 页面组件体系 | `AnalysisFilterBar` / `BaseChart` / `content-card` / `el-table` / `el-drawer` | 与学情画像/预警页风格一致 |
| 报告导出 | `backend/app/api/v1/report.py` + `algorithm/src/reporter.py` | 导出 PDF/Excel 时复用双轨增强 |
| 会话记忆 | `backend/app/services/agent/memory.py` | 追问时继承诊断上下文(6 轮) |

### 4.2 新建

| 层 | 文件 | 说明 |
|---|---|---|
| 菜单 | `frontend/src/config/menu.ts` | "智能分析" children 加 `{ path: '/analysis/diagnosis', title: 'AI 学情分析', icon: 'MagicStick' }`;`routeTitleMap` / `routeParentMap` 加映射(改 3 处) |
| 路由 | `frontend/src/router/index.ts` | AppLayout children 加路由(`meta.roles: ['teacher']`,组件指向 DiagnosisView) |
| 前端视图 | `frontend/src/views/analysis/DiagnosisView.vue` | 主页面,仿 StudentProfileView,组合 FilterBar + Process + Report |
| 前端组件 | `frontend/src/components/analysis/DiagnosisProcess.vue` | SSE 过程展示(抽 AgentChat 的 toolCalls 区,可折叠) |
| 前端组件 | `frontend/src/components/analysis/DiagnosisReport.vue` | 结构化报告渲染(班级版 + 学生版两套布局) |
| 前端 API | `frontend/src/api/analysis.ts` 加 `streamDiagnosis` | 复用 SSE 消费逻辑,带 agent_type=diagnosis |
| 后端 prompt | `backend/app/services/agent/prompts/diagnosis.py` | **核心新建**:DIAGNOSIS_SYSTEM_PROMPT(指示主动编排工具 + 输出结构化 JSON) |
| 后端装配 | `backend/app/api/v1/agent.py` 的 `_resolve_agent_setup` | 加 `agent_type="diagnosis"` 分支,挂全部查询工具 |

### 4.3 实现路径选择

**不新建独立诊断端点,直接复用 `/agent/chat/stream` + 新增 `agent_type=diagnosis`。**

理由:诊断本质就是"AI 自动编排多工具 + 综合输出",正是 Agent FC 循环的用法,新建 `/api/v1/diagnosis/generate` 端点是重复造轮子。前端 `streamDiagnosis` 只是 `streamAgentChat` 的语义化封装(固定 agent_type + 预设首条 message)。

**DIAGNOSIS_SYSTEM_PROMPT 要点:**
1. 角色定位:你是学情诊断专家,任务是**主动**调用工具全面收集数据后做综合诊断(而非等用户问什么答什么)。
2. 工具编排策略:按分析维度依次调用 get_course_overview → get_weak_knowledge_points → get_warning_students → get_score_trend →(学生视角加 get_student_detail / get_knowledge_mastery)。
3. 输出格式:最终 content 必须是结构化 JSON(见 §5),不是自由文本。
4. 数据引用:每个发现/归因要带 evidence 和 dataRef(引用的工具名),保证可追溯。
5. 干预建议:每条建议带 priority + toolHint(薄弱点驱动出题 / 发通知 / 约谈)。

---

## 5. 诊断报告数据结构

AI 最终 `content` 返回的结构化 JSON(前端按此渲染):

```json
{
  "scope": "class",
  "overall": {
    "grade": "B",
    "score": 78,
    "summary": "整体稳定,图论为突出短板,3 名学生需重点关注"
  },
  "findings": {
    "strengths": [
      { "point": "课堂参与度", "value": "92%", "evidence": "班级互动数据,年级前列" }
    ],
    "risks": [
      { "level": "高", "subject": "图论掌握度 42%", "evidence": "实验报告失分占 58%", "students": ["张三","李四"] }
    ]
  },
  "causes": [
    { "issue": "图论薄弱", "rootCause": "实验扣分集中在该模块", "dataRef": "get_weak_knowledge_points" }
  ],
  "suggestions": [
    {
      "action": "图论专项复习",
      "priority": "高",
      "toolHint": "weakness_driven_quiz",
      "target": "全班",
      "knowledgePoints": ["图论"]
    }
  ],
  "radar": { "成绩": 72, "考勤": 96, "互动": 92, "进步": 70, "综合": 78 },
  "meta": { "source": "llm", "toolsUsed": ["get_course_overview","get_weak_knowledge_points"] }
}
```

学生视角结构相同,`scope: "student"`,额外字段:
- `studentInfo`:学号/姓名/班级
- `scoreHistory`:历次成绩数组(渲染趋势小图)
- `attitudeDetail`:出勤/互动/作业得分(渲染态度构成)

---

## 6. 结果去向(干预闭环)

诊断报告底部三个动作:

| 动作 | 实现 | 跳转目标 |
|---|---|---|
| 💬 追问 AI | 走 `/agent/chat/stream`(agent_type=qa,同 session_id) | 报告区下方展开输入框,继承诊断上下文 |
| 📄 导出报告 | 调 `report.py` 的 PDF/Excel 导出,把诊断 JSON 塞进 ReportContext | 下载文件(复用 `_snapshot_pdf` / `_snapshot_workbook`) |
| 📋 生成干预任务 | 按 suggestions 的 toolHint 路由 | `weakness_driven_quiz` → AI 出题页(注入 knowledgePoints) / `notify` → 预警发通知 / `talk` → 预警详情 |

**干预闭环示意(对应 MVP v1.1 旗舰 C1→A3):**
```
班级诊断 → 薄弱点 Top5(图论42%) → [生成干预任务] → AI出题(注入图论) → 学生答题 → 掌握度回流 → 下次诊断图论↑
```

---

## 7. 实现清单(落地步骤)

### 阶段 1:后端 prompt + 装配(核心)
1. 新建 `backend/app/services/agent/prompts/diagnosis.py`,写 DIAGNOSIS_SYSTEM_PROMPT
2. `agent.py` 的 `_resolve_agent_setup` 加 `diagnosis` 分支,挂全部查询工具
3. 用 MockLLMProxy 跑通 FC 循环,验证工具编排顺序

### 阶段 2:前端页面骨架
4. `menu.ts` + `router/index.ts` 加菜单和路由(改 3 处)
5. 新建 `DiagnosisView.vue`(仿 StudentProfileView,组合 FilterBar + 占位区)
6. 新建 `DiagnosisProcess.vue`(SSE 过程展示,抽 AgentChat toolCalls 区)

### 阶段 3:报告渲染
7. 新建 `DiagnosisReport.vue`(班级版 + 学生版两套布局)
8. `api/analysis.ts` 加 `streamDiagnosis`(封装 SSE 消费)
9. 联调:选班级 → 开始分析 → 过程实时 → 报告渲染

### 阶段 4:结果联动
10. 追问输入框(复用 AgentChat 输入逻辑)
11. 导出按钮(调 report.py)
12. 生成干预任务(按 toolHint 路由跳转)

### 阶段 5:测试
13. 后端:`tests/test_diagnosis_agent.py`(FC 循环集成 + prompt 输出格式校验)
14. 前端:联调班级/学生两个视角,验证 SSE 流式 + 报告渲染 + 联动跳转

---

## 8. 关键路径文件

| 文件 | 作用 |
|---|---|
| `frontend/src/config/menu.ts` | 菜单配置(加菜单项 + routeTitleMap + routeParentMap) |
| `frontend/src/router/index.ts` | 路由配置 |
| `frontend/src/views/analysis/StudentProfileView.vue` | 画像页布局范本 |
| `frontend/src/views/analysis/WarningView.vue` | 预警页布局范本(统计卡 + 列表 + drawer) |
| `frontend/src/components/agent/AgentChat.vue` | 对话渲染组件(过程区参考其 toolCalls) |
| `frontend/src/api/agent.ts` | 前端 SSE 调用(streamAgentChat) |
| `backend/app/services/agent/base.py` | Agent FC 循环(run_agent_stream) |
| `backend/app/services/agent/tools/queries.py` | 10 个学情查询工具 |
| `backend/app/services/agent/prompts/qa.py` | QA prompt 范本(diagnosis prompt 参考其结构) |
| `backend/app/api/v1/agent.py` | Agent API 端点(_resolve_agent_setup) |
| `backend/app/api/v1/report.py` | 报告导出(复用 PDF/Excel) |
| `backend/app/services/report_template.py` | ReportContext + 模板兜底 |
| `algorithm/src/reporter.py` | LLM 报告增强(双轨) |

---

## 9. 待确认 / 风险

- **诊断深度与工具调用次数:** max_steps 默认 5,班级诊断要调 5-6 个工具,可能不够。建议 diagnosis 的 max_steps 调到 8-10,或允许单步并行多工具。
- **LLM 输出格式稳定性:** 要求 LLM 输出严格 JSON 有概率失败。前端需做 JSON 解析兜底,失败时把 content 当纯文本展示 + 提示"诊断报告格式异常,可追问"。
- **导出复用:** report.py 现有 ReportContext 是模板导向,诊断 JSON 结构不同。导出时需做一层适配(诊断 JSON → ReportContext 三段式),或单独加一个诊断导出端点。倾向前者(适配层),避免端点膨胀。
- **权限:** 复用 `_check_course_access` / `_check_profile_access`,diagnosis agent_type 限 teacher,工具调用时 ToolContext 带 course_id 隔离(与 qa 一致)。
