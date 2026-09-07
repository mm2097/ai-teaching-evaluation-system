# AI 学情分析 — 开发文档 v1.0

> **文档定位**:面向开发者的可执行落地文档,在 `AI学情分析Agent设计方案_v1.0.md`(设计稿)与 `AI学情分析验收测试集_v1.0.md`(48 用例)之间补上"怎么写代码"这一层。
> **输入**:`AI学情分析_原型_v1.0.html`(视觉/交互)、设计方案(架构)、验收测试集(验收点)、真实代码结构(探查结论)。
> **范围**:前端链路(正常/异常/权限预期行为)+ Agent 能力对应的测试输入输出 + 后端 prompt/装配/导出适配/测试。
> **日期**:2026-09-07

---

## 0. 文档使用说明

本文档**以代码现状为准**。设计方案里若干假设经代码探查后与现状不符,这些差异已标注为 ⚠️ **现状偏差**,实现时以本文档为准(要么改代码、要么改预期)。每个章节末尾的【落地清单】可直接作为 commit 粒度的任务拆分依据。

读者顺序建议:第 1 节看全貌 → 第 2 节看接口契约 → 第 3 节写后端 → 第 4 节写前端 → 第 5 节对照测试输入输出 → 第 6 节兜底/权限 → 第 7 节联调。

---

## 1. 全貌与现状偏差

### 1.1 功能一句话

老师选班级或学生 → 点"开始 AI 分析" → 后端 Agent 主动编排多个学情查询工具拉全量数据 → 输出结构化 JSON 诊断报告(总体评估+关键发现+归因+干预建议)→ 前端 SSE 流式渲染过程与报告 → 可追问/导出/生成干预任务。

### 1.2 复用 vs 新建(代码探查确认)

| 能力 | 现状 | 复用结论 |
|---|---|---|
| 10 个学情查询工具 | `backend/app/services/agent/tools/queries.py:673` `register_query_tools` 已注册 10 个 | ✅ 全部复用,**无需新建工具** |
| Agent FC 循环 | `base.py:126` `run_agent` / `base.py:316` `run_agent_stream` | ✅ 复用 |
| SSE 序列化 | `agent.py:113` `data: {json}\n\n`,事件名在 payload `type` 字段 | ✅ 复用 |
| 前端 SSE 消费 | `frontend/src/api/agent.ts:74` `streamAgentChat`(async generator) | ✅ 复用,封装 `streamDiagnosis` |
| 会话记忆 | `memory.py:102` 进程内字典,6 轮窗口 | ✅ 追问复用 |
| 报告导出 | `report.py` 的 `_snapshot_pdf`/`_snapshot_workbook` | ⚠️ 只认 `summary/conclusion/suggestion` 三字段,**需适配层** |
| 页面组件 | `AnalysisFilterBar`(`components/common/`)、`BaseChart`、`content-card` | ✅ 复用 |
| `_resolve_agent_setup` | `base.py:42-58`,现有 `qa`/`exam`/`tutor` 三分支 | 🔨 **需加 `diagnosis` 分支** |

### 1.3 ⚠️ 现状偏差清单(实现前必读)

| # | 设计方案假设 | 代码现状 | 处置 |
|---|---|---|---|
| D1 | "权限复用 `_check_course_access`/`_check_profile_access`,diagnosis 限 teacher" | 这两个函数定义在 `analysis.py:180`/`:103`,**`agent.py` 完全没 import、没调用**;chat 端点只有 `get_current_user`,任何登录用户可调 | 🔨 **必须在 agent 端点补权限校验**,否则验收 TC-DIAG-SAFE-04~06 全挂(见 §6.2) |
| D2 | "diagnosis 的 max_steps 调到 8-10" | `agent.py:37` `max_steps: int = Field(ge=1, le=8)`,**硬上限 8** | 🔨 提升上限到 10(`le=10`),或 diagnosis 走 8(够调 5-6 个工具) |
| D3 | "追问继承诊断上下文(含工具调用)" | `memory.py` 的 `ConversationTurn` **不存 tool_calls/tool_results**(base.py:264/423 传空),记忆里只有最终文本 | 📝 **预期校准**:追问能继承"诊断结论文本",但 LLM 看不到上轮工具原始结果,需重新调工具。验收 TC-DIAG-ASK-01 的"不重新拉全量数据"应理解为"不重新做完整诊断",追问触发新工具调用是允许的(ASK-02 正要求如此) |
| D4 | "SSE 事件 step_start/tool_call/tool_result/content/done" | 后端确实发这 5 个 + `error`;但 `done` 带 `answer` 字段、`error` 后**不发 done**;前端 `streamAgentChat` **丢弃 done 事件** | 📝 前端不要依赖 done 携带的数据(token/耗时拿不到);用 `content` 事件作为"报告就绪"信号 |
| D5 | "前端过程区仿 AgentChat toolCalls" | AgentChat 的 `tool_result.callId` 用模块级计数器拼(`agent.ts:123`),并发多工具会错配 | 📝 DiagnosisProcess 组件**自带 callId 匹配**(见 §4.3),不复用 streamAgentChat 的脆弱逻辑;或封装 `streamDiagnosis` 时修正 callId |
| D6 | "导出复用 report.py,诊断 JSON 塞进 ReportContext" | `_snapshot_pdf`/`_snapshot_workbook` 只读 `summary/conclusion/suggestion`,诊断 JSON 是 `overall/findings/causes/suggestions` 结构 | 🔨 **写适配层** `_diagnosis_to_report_fields(diagnosis_json)`(见 §3.4) |
| D7 | "conftest 种子: C001/S001-S030/6 知识点(哈夫曼/线索)/S020 红色预警" | conftest 现状: 3 学生(张三/李四/王五)、4 知识点(二叉树/红黑树/快排/归并)、张三有 1 条 level-2 预警 | 🔨 **扩展种子或降级金标准**(见 §5.1)。张三 85→75→55 下滑+红黑树 mastery=30 是现成的"下滑+薄弱"原型 |

---

## 2. 接口契约(SSE 事件 + 请求/响应)

### 2.1 端点(复用,不新建)

```
POST /api/v1/agent/chat/stream   agent_type=diagnosis
POST /api/v1/agent/chat          agent_type=diagnosis(同步,非主流式)
DELETE /api/v1/agent/session/{session_id}   清会话
```

**不新建 `/api/v1/diagnosis/generate`**。diagnosis 本质是"Agent 自动编排多工具+综合输出",复用 FC 循环即可。前端 `streamDiagnosis` 是 `streamAgentChat` 的语义化封装(固定 `agent_type="diagnosis"` + 预设首条 message)。

### 2.2 请求体(`AgentChatRequest`,`agent.py:29-37`)

```json
{
  "message": "请对班级做全面学情诊断",
  "course_id": 1,
  "student_id": null,
  "session_id": "diagnosis_c1",
  "agent_type": "diagnosis",
  "max_steps": 8
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `message` | str | 必填。诊断场景由前端按"分析对象+维度+深度"拼装(见 §4.4) |
| `course_id` | int | 必填。课程隔离依据,透传进 ToolContext |
| `student_id` | int\|null | 学生诊断时传,班级诊断传 null |
| `session_id` | str | 不传则后端兜底 `u{uid}_c{cid}_default`;追问复用同一 session_id |
| `agent_type` | str | 固定 `"diagnosis"` |
| `max_steps` | int | 默认 5,**诊断建议前端传 8**;⚠️ 现状 `le=8`,需改 `le=10`(§3.2) |

### 2.3 SSE 事件流(后端真实产出,`base.py:358-432`)

序列化格式:`data: {jsonpayload}\n\n`,payload 含 `type` 字段区分。**前端按下表消费**:

| 事件 type | 触发 | payload | 前端用途 |
|---|---|---|---|
| `step_start` | 每个 FC 步开始 | `{type, step:int}` | 过程区新增一步占位 |
| `tool_call` | 工具执行**前** | `{type, step, name:str, arguments:dict}` | 过程区渲染工具行(运行中) |
| `tool_result` | 工具执行**后** | `{type, step, name:str, result:dict, elapsed_ms:int}` | 过程区工具行转完成,写摘要 |
| `content` | LLM 无 tool_calls(最终答案) | `{type, step, content:str}` | **报告就绪信号**,content 是诊断 JSON 字符串,前端 `JSON.parse` |
| `done` | 正常结束(含 truncated) | `{type, total_elapsed_ms, total_tokens, truncated:bool, answer:str}` | ⚠️ 前端 streamAgentChat 丢弃;DiagnosisView 不依赖它 |
| `error` | LLM 异常/循环异常 | `{type, message:str}` | ⚠️ **error 后不再有 done**,前端见 error 即终止并展示重试 |

关键规则:
- `content` 只发一次(无 tool_calls 那步),发完即 break,紧跟 done。
- `error` 与 `done` 互斥,error 路径直接 return。
- truncated(步数耗尽)时**不发 content**,done 的 `answer` 为空串 → 前端要兜底(§4.5 异常链路)。
- 工具结果回灌截断到 4000 字符(`base.py:408`)。

### 2.4 诊断报告 JSON 结构(AI 最终 content,前端按此渲染)

```json
{
  "scope": "class",
  "overall": { "grade": "B", "score": 78, "summary": "整体稳定,图论为突出短板" },
  "findings": {
    "strengths": [
      { "point": "课堂参与度", "value": "92%", "evidence": "互动数据年级前列" }
    ],
    "risks": [
      { "level": "高", "subject": "图论掌握度 42%", "evidence": "实验失分占58%", "students": ["张三"] }
    ]
  },
  "causes": [
    { "issue": "图论薄弱", "rootCause": "实验扣分集中该模块", "dataRef": "get_weak_knowledge_points" }
  ],
  "suggestions": [
    { "action": "图论专项复习", "priority": "高", "toolHint": "weakness_driven_quiz",
      "target": "全班", "knowledgePoints": ["图论"] }
  ],
  "radar": { "成绩": 72, "考勤": 96, "互动": 92, "进步": 70, "综合": 78 },
  "meta": { "source": "llm", "toolsUsed": ["get_course_overview","get_weak_knowledge_points"] }
}
```

学生视角 `scope:"student"`,额外:`studentInfo`(学号/姓名/班级)、`scoreHistory`(数组,趋势小图)、`attitudeDetail`(出勤/互动/作业)。

**字段约束(对应验收)**:`overall`/`findings`/`causes`/`suggestions`/`radar`/`meta` 六顶层齐全(CLASS-01);`suggestions` 每条带 `priority`+`toolHint`(CLASS-06);`causes` 每条带 `dataRef`(CLASS-07);`toolHint ∈ {weakness_driven_quiz, notify, talk}`(ACT-01~03)。

---

## 3. 后端实现

### 3.1 新建 `backend/app/services/agent/prompts/diagnosis.py`

仿 `qa.py` 四段式结构(角色→流程→铁律→技能映射),但**强制输出 JSON**。要点:

```python
DIAGNOSIS_SYSTEM_PROMPT = """你是一名「学情诊断专家」,服务于高校计算机学院任课教师。

# 工作流程(主动诊断,非问答)
1. 根据用户请求中的【分析对象】【分析维度】【深度】,主动调用学情查询工具全面收集数据
2. 综合分析数据,识别优势与风险,做归因,给干预建议
3. 最终输出必须是严格 JSON(结构见下),不要输出任何 JSON 以外的文字

# 工具编排策略(按分析对象)
## 班级诊断(detail 深度)
- get_course_overview(总览先行,必调)
- get_weak_knowledge_points(知识点薄弱,必调)
- get_knowledge_mastery(知识点掌握度)
- get_warning_students(预警,勾选"预警"维度时调)
- get_score_trend(成绩趋势,勾选"成绩"时调)
- get_attendance(考勤,勾选"考勤"时调)
## 学生诊断
- get_student_detail(学生综合档案,必调)
- get_score_trend(student_id=该生)
- get_knowledge_mastery(student_id=该生)
- get_weak_knowledge_points
- get_exercise_records(勾选"答题"时调)
## 概览深度(brief):只调前 3 个工具
## 维度勾选:只调勾选维度对应的工具,不越界

# 铁律
1. 严禁编造:所有数字/人名/知识点必须来自工具返回,不得臆测
2. dataRef 必须是真实调用过的工具名
3. suggestions 的 toolHint 只能是 weakness_driven_quiz / notify / talk 三者之一
4. 数据不足时,在对应 findings/causes 写"数据不足",不要硬编
5. 输出纯 JSON,无 markdown 代码块,无前后缀文字

# 输出 JSON 结构
{ "scope":"class|student", "overall":{...}, "findings":{...},
  "causes":[...], "suggestions":[...], "radar":{...}, "meta":{...} }
(完整字段定义见开发文档 §2.4)
"""
```

落地:`prompts/__init__.py:7-9` 加 `from .diagnosis import DIAGNOSIS_SYSTEM_PROMPT`。

### 3.2 `base.py:42-58` `_resolve_agent_setup` 加 diagnosis 分支

```python
def _resolve_agent_setup(agent_type, registry, allow_mutation):
    if agent_type == "exam":
        return EXAM_SYSTEM_PROMPT, registry.to_openai_schemas(agent="both", include_mutation=allow_mutation)
    if agent_type == "tutor":
        return TUTOR_SYSTEM_PROMPT, []
    if agent_type == "diagnosis":                          # 新增
        return DIAGNOSIS_SYSTEM_PROMPT, registry.to_openai_schemas(
            agent="both", include_mutation=False)          # 诊断只读,不挂写工具
    return QA_SYSTEM_PROMPT, registry.to_openai_schemas(agent="both", include_mutation=allow_mutation)
```

**工具集说明**:诊断挂全部 10 个查询工具(`agent="both"` 会纳入查询工具)。⚠️ 注意 `exam.py` 的 8 个组卷工具也标了 `agent="both"`,会一起被纳入。如需限制诊断只挂查询工具,需在 `registry` 增加按 category 过滤的能力,或在 diagnosis 分支手动过滤掉 exam 工具名。**MVP 阶段建议不过滤**(组卷工具对诊断无害,LLM 不会主动调),降低改动面。

同步改 `agent.py:37`:`max_steps: int = Field(ge=1, le=10)`(从 8 提到 10,解决 D2)。

### 3.3 ⚠️ 补权限校验(解决 D1,验收 SAFE-04~06 的前提)

`agent.py` 的 `/agent/chat` 和 `/agent/chat/stream` 当前只用 `get_current_user`。诊断是 teacher 功能,**必须补**:

```python
# agent.py 顶部 import
from app.api.v1.analysis import _check_course_access, _check_profile_access

# 两个 chat 端点内,拿到 user 和 course_id 后:
if agent_type == "diagnosis":
    if user.role != "teacher":
        raise HTTPException(403, "仅教师可使用 AI 学情诊断")
    if course_id:
        _check_course_access(session, user, course_id)   # 复用 analysis.py 的现成函数
    if student_id:
        _check_profile_access(session, user, student_id, course_id)
```

> `_check_course_access`(`analysis.py:180`):教师只能看自己授课课程,学生无权,违者 403。
> `_check_profile_access`(`analysis.py:103`):学生只能看自己,教师只能看授课课程内学生。
> 这两个函数已存在且被 eval/report 复用,直接调用即可。

**注意**:只对 `diagnosis` agent_type 加校验,不动 qa/exam/tutor 的现有行为(避免回归)。学生角色在路由层也会被拦(`meta.roles:['teacher']`,见 §4.2),这是双保险。

### 3.4 导出适配层(解决 D6)

现有 `_snapshot_pdf`/`_snapshot_workbook` 只认 `summary/conclusion/suggestion`。诊断 JSON 结构不同,写适配函数:

```python
# report.py 新增
def _diagnosis_to_report_fields(diag: dict) -> dict:
    """诊断 JSON → 报告三段式字段,缺字段用 '-' 兜底(TC-DIAG-EXPORT-04)"""
    overall = diag.get("overall", {})
    findings = diag.get("findings", {})
    causes = diag.get("causes", [])
    suggestions = diag.get("suggestions", [])

    summary = overall.get("summary") or "-"

    # conclusion: 关键发现 + 归因 拼接
    parts = []
    for r in findings.get("risks", []):
        parts.append(f"[风险] {r.get('subject','-')}:{r.get('evidence','-')}")
    for s in findings.get("strengths", []):
        parts.append(f"[优势] {s.get('point','-')}:{s.get('value','-')}")
    for c in causes:
        parts.append(f"[归因] {c.get('issue','-')}:{c.get('rootCause','-')}(来源:{c.get('dataRef','-')})")
    conclusion = "\n".join(parts) or "-"

    # suggestion: 建议列表拼接
    sug_lines = [f"[{s.get('priority','-')}] {s.get('action','-')}(工具:{s.get('toolHint','-')})"
                 for s in suggestions]
    suggestion = "\n".join(sug_lines) or "-"

    return {"summary": summary, "conclusion": conclusion, "suggestion": suggestion,
            "source": "diagnosis", "scope": diag.get("scope", "class")}
```

**导出端点选择**:倾向复用现有 `GET /report/history/{id}/download`(快照导出)。流程:诊断完成 → 前端把诊断 JSON POST 到一个新端点 `POST /report/diagnosis`(或复用 `/report/history` 带 `report_type=5 诊断`)→ 后端调 `_diagnosis_to_report_fields` → 存 ReportHistory → 返回 history_id → 前端用 history_id 调 download。

> ⚠️ 是否新增 `report_type=5` 需在 `report.py:54-66` 的 `_REPORT_TYPE_SCOPE`/`_REPORT_TYPE_NAMES` 加映射。这是最小改动路径。若想完全避免改 report.py 的类型枚举,可单独加 `/report/diagnosis/export` 端点直接渲染下载。**推荐前者**(加 report_type=5),保持导出管线统一。

### 3.5 后端落地清单

- [ ] 新建 `prompts/diagnosis.py`(DIAGNOSIS_SYSTEM_PROMPT),`__init__.py` 导出
- [ ] `base.py:_resolve_agent_setup` 加 `diagnosis` 分支(挂查询工具,`include_mutation=False`)
- [ ] `agent.py:37` `max_steps` 上限改 `le=10`
- [ ] `agent.py` 两个 chat 端点加 diagnosis 权限校验(import `_check_course_access`/`_check_profile_access`)
- [ ] `report.py` 加 `_diagnosis_to_report_fields` 适配函数 + `report_type=5` 映射 + 诊断存快照端点
- [ ] 用 MockLLMProxy 跑通 FC 循环,验证工具编排顺序(§5)

---

## 4. 前端实现

### 4.1 路由与菜单(改 3 处)

**`frontend/src/config/menu.ts`**(智能分析 children,现 4 项,`menu.ts:38-49`):
```ts
// children 加
{ path: '/analysis/diagnosis', title: 'AI 学情分析', icon: 'MagicStick' }
// routeTitleMap 加(menu.ts:138-166)
'/analysis/diagnosis': 'AI 学情分析'
// routeParentMap 加(menu.ts:169-194)
'/analysis/diagnosis': { path: '/analysis', title: '智能分析' }
```

**`frontend/src/router/index.ts`**(analysis 段,`index.ts:56-80`):
```ts
{
  path: 'analysis/diagnosis',
  name: 'Diagnosis',
  component: () => import('@/views/analysis/DiagnosisView.vue'),
  meta: { title: 'AI 学情分析', roles: ['teacher'] }   // 路由层权限(双保险)
}
```

### 4.2 视图组件结构(`DiagnosisView.vue`,仿 StudentProfileView)

```
.page-container
├── .content-card                         ← 筛选栏卡
│   └── <AnalysisFilterBar ... @query="onQuery" />
│       (v-model:target-type 班级/学生切换,useAnalysisScope 驱动)
├── .content-card(维度+深度+开始按钮,内联,原型 .filter-row)
│   维度 chips:成绩/考勤/知识点/预警/答题(多选)
│   深度:详细/概览
│   [🤖 开始 AI 分析](disabled = running || 无 courseId)
├── .content-card  过程区
│   └── <DiagnosisProcess :steps="processSteps" :running="running" :error="processError" />
└── .content-card  报告区(v-if="report")
    └── <DiagnosisReport :report="report" :scope="scope" @ask="onAsk" @export="onExport" @act="onAct" />
```

**AnalysisFilterBar 实际路径**:`components/common/AnalysisFilterBar.vue`(⚠️ 不是 `components/analysis/`,D5 相关)。props/emits 见 §4.6。分析对象切换由 `useAnalysisScope('class'|'student')` composable 驱动,不是组件内部做。

### 4.3 `DiagnosisProcess.vue`(过程区,抽 AgentChat toolCalls 结构)

**不复用 `streamAgentChat` 的 callId 拼接逻辑**(D4/D5 脆弱)。组件自带状态管理:

```ts
// props
defineProps<{ steps: ProcessStep[]; running: boolean; error?: string }>()
// ProcessStep = { step: number; toolCalls: ToolCall[]; status: 'running'|'done' }
// ToolCall = { id: string; name: string; arguments: dict; result?: dict; summary?: string; status: 'running'|'done'|'error' }
```

渲染(仿 `AgentChat.vue:227-240`):
- `.step` 行:`✓/◐` 图标 + 工具名 + 摘要 + 状态 tag(运行中/完成/失败)
- 「展开查看原始数据」折叠区:`<pre>` 显示 `JSON.stringify(result, null, 2)`,深色背景
- 顶部"AI 正在诊断…"转圈(running 时)/"诊断完成,共调用 N 个工具"(done)

**callId 匹配修正**:DiagnosisView 消费 SSE 时,**用 `step + name` 组合键**匹配 tool_call 和 tool_result(而非 streamAgentChat 的计数器)。在同一步内同名工具并发时再加序号。

### 4.4 `streamDiagnosis` 封装(`api/analysis.ts` 新增)

```ts
export async function* streamDiagnosis(params: {
  courseId: number
  studentId?: number
  scope: 'class' | 'student'
  dimensions: string[]   // ['score','attendance','knowledge','warning','exercise']
  depth: 'detail' | 'brief'
  sessionId?: string
}): AsyncGenerator<DiagEvent> {
  const message = buildDiagnosisMessage(params)  // 拼装首条消息
  const stream = streamAgentChat({
    message, courseId: params.courseId, agentType: 'diagnosis' as AgentType,
    sessionId: params.sessionId ?? `diagnosis_c${params.courseId}`,
    maxSteps: 8,
  })
  for await (const evt of stream) {
    // 透传 thinking/tool_call/tool_result/content_done/error
    // 修正 callId:用 step+name 匹配(见 §4.3)
    yield evt as DiagEvent
  }
}

function buildDiagnosisMessage(p): string {
  const dims = p.dimensions.join('、')
  const target = p.scope === 'student' ? `学生(student_id=${p.studentId})` : '班级'
  const depth = p.depth === 'brief' ? '概览(只调3个核心工具)' : '详细'
  return `请对${target}做${depth}学情诊断,分析维度:${dims}。按工具编排策略调用学情工具,输出结构化JSON诊断报告。`
}
```

> ⚠️ `AgentType` 现状是 `'qa'|'exam'|'tutor'`(`types/index.ts`),需加 `'diagnosis'`。`streamAgentChat` 的 `max_steps` 硬编码 5(`agent.ts:61-67`),要么改 streamAgentChat 接受 maxSteps 参数,要么 streamDiagnosis 绕过它直接 fetch(推荐前者,小改 streamAgentChat 加可选 `maxSteps`)。

### 4.5 前端链路预期行为(正常/异常/权限)★重点

#### 4.5.1 正常链路

| 阶段 | 触发 | 预期 UI | 数据流 |
|---|---|---|---|
| 空状态 | 进入页面 | 过程区引导卡"选择分析对象与维度,点击开始 AI 分析"+ 快捷场景按钮;报告区隐藏 | — |
| 选范围 | 选学期/课程/班级(或切学生选人) | AnalysisFilterBar 联动,学生选择器随 target-type 显隐 | `useAnalysisScope` 更新 queryParams |
| 点开始 | click「开始 AI 分析」 | 按钮 disabled;过程区显示"AI 正在诊断…"+ 空 step 列表;报告区骨架屏 | 调 `streamDiagnosis`,sessionId=`diagnosis_c{cid}` |
| 工具执行 | 收 `tool_call` → `tool_result` | step 列表逐行出现,运行中→完成,写摘要;可展开原始数据 | processSteps 累加 |
| 报告就绪 | 收 `content` 事件 | 过程区顶部"诊断完成,共调用 N 个工具";报告区渲染(班级版/学生版) | `JSON.parse(content)` → report |
| 追问 | 点「💬 追问 AI」展开输入框,回车发送 | 报告下方气泡:用户问(右)+ AI 答(左) | 走 `streamAgentChat(agentType='qa', sessionId 同诊断)`,继承文本上下文 |
| 导出 | 点「📄 导出报告」选 PDF/Excel | 触发下载 | POST 诊断 JSON → 后端适配 → 下载 |
| 干预 | 点建议的「生成练习」/「发通知」/「生成干预任务」 | 跳转 AI 出题页(注入知识点)/ 调预警通知 / 聚合任务 | 按 `toolHint` 路由 |

#### 4.5.2 异常链路

| 场景 | 触发方式 | 预期 UI | 不允许的表现 |
|---|---|---|---|
| **LLM 不可达**(8001 挂) | 断 algorithm 服务 | 过程区显示已调工具;报告区降级提示"诊断服务暂不可用,可重试"+ [重新分析] | ❌ 不白屏、不 500 |
| **LLM 输出非 JSON** | content 不是合法 JSON | `JSON.parse` 失败 → 报告区降级为纯文本展示 content + 提示"报告格式异常,可追问" | ❌ 不白屏 |
| **truncated**(步数耗尽) | max_steps 用尽,无 content 事件 | done.answer 为空 → 报告区"诊断未完成(已达最大推理步数),可重试或缩小维度" | ❌ 不卡死 |
| **单工具失败** | 某工具返回 `{error:...}` | 过程区该工具行标红"失败";诊断继续(其他工具照常);报告标注"部分数据缺失" | ❌ 不中断整条流 |
| **SSE 断流** | 诊断中关后端连接 | "诊断中断,可重试" | ❌ 不白屏 |
| **空班级** | 选无学生班级 | 过程区可能只调 1 个工具;报告区"该班级暂无学情数据" | ❌ 不 500、不卡死 |
| **重复点击** | 分析中再点开始 | 按钮 disabled(从开始到报告就绪/失败) | ❌ 不发第二个请求 |

> 关键实现:DiagnosisView 用 `running` ref 锁按钮;`content` 事件 try/catch JSON.parse,失败走文本降级;`error` 事件设 processError 并解锁按钮;`finally` 兜底"未收到有效回复"。

#### 4.5.3 权限链路

| 场景 | 拦截层 | 预期 |
|---|---|---|
| **学生访问** | 路由守卫(`meta.roles:['teacher']`,`router/index.ts:209-237`)+ 后端 diagnosis 角色校验 | 学生登录 → 路由层重定向到其默认页;若绕过路由直接调 API → 后端 403 |
| **非授课教师** | 后端 `_check_course_access` | 403,前端提示"无权访问该课程" |
| **课程隔离** | ToolContext.course_id + 工具内 `_resolve_course_id` | 教师只能拉到自己授课课程的数据,工具层兜底 |

> ⚠️ 现状 chat 端点无权限校验(D1),**权限链路预期行为依赖 §3.3 先落地**。在 §3.3 完成前,TC-DIAG-SAFE-04~06 无法通过。前端要对 403 响应统一处理(ElMessage.error + 不渲染报告)。

### 4.6 AnalysisFilterBar 接口(复用,`components/common/`)

| 关键 prop/emit | 用途 |
|---|---|
| `v-model:target-type` | `'student'\|'class'`,分析对象切换 |
| `v-model:course-id` / `v-model:class-id` / `v-model:target-id` | 选中的课程/班级/学生 |
| `:show-student-picker` | 学生选择器显隐(composable 按 targetType 算) |
| `:show-query-button="true"` + `@query` | 触发查询(DiagnosisView 用 @query 加载选项,非直接诊断) |
| `allowed-target-types` | 限制可选分析对象(diagnosis 两种都支持) |

> DiagnosisView 不直接用 AnalysisFilterBar 的 @query 触发诊断(诊断由"开始 AI 分析"按钮触发),@query 仅用于切换课程时重置过程区与报告区。

### 4.7 前端落地清单

- [ ] `menu.ts` 加菜单项 + routeTitleMap + routeParentMap(3 处)
- [ ] `router/index.ts` 加 `/analysis/diagnosis` 路由(`roles:['teacher']`)
- [ ] `types/index.ts` `AgentType` 加 `'diagnosis'`
- [ ] `agent.ts` `streamAgentChat` 加可选 `maxSteps` 参数(诊断传 8)
- [ ] `api/analysis.ts` 加 `streamDiagnosis` + `buildDiagnosisMessage`
- [ ] 新建 `views/analysis/DiagnosisView.vue`(仿 StudentProfileView,组合三卡)
- [ ] 新建 `components/analysis/DiagnosisProcess.vue`(过程区,自带 callId 匹配)
- [ ] 新建 `components/analysis/DiagnosisReport.vue`(班级版+学生版两套布局)
- [ ] 异常链路:JSON.parse 兜底、error 事件处理、running 锁、truncated 提示
- [ ] 追问框(复用 AgentChat 输入逻辑,agentType='qa' 同 sessionId)
- [ ] 导出按钮(调诊断导出端点)、干预按钮(按 toolHint 路由跳转)

---

## 5. Agent 能力 → 测试输入输出(对应验收用例)★重点

本节把 Agent 的每个能力点映射到**可执行的测试输入与预期输出**,直接对应 `test_diagnosis_agent.py` 与验收测试集。测试范式照 `test_rag_exam_agent.py`:L1 工具单测(直接调 `_t_xxx`) + L2 FC 循环(MockLLMProxy 脚本化)。

### 5.1 种子数据策略(先决,对应 D7)

**现状**:conftest 3 学生(张三 S1/李四 S2/王五 S3)、4 知识点(二叉树/红黑树/快排/归并)、张三 85→75→55 下滑 + 红黑树 mastery=30 + 1 条 level-2 预警。

**两种策略二选一**(实现前确认):

- **策略 A(降级金标准,推荐 MVP)**:复用现有 conftest,把验收金标准映射到现有数据:
  - 下滑学生 = 张三(S1),85→75→55(`conftest.py:119-121`)
  - 稳定学生 = 李四(S2),70→72→68
  - 进步学生 = 王五(S3),60→70→80
  - 薄弱知识点 = 红黑树(张三 mastery=30,`conftest.py:164`)
  - 预警学生 = 张三(W1 成绩下滑 level=2,`conftest.py:267`)
  - 验收文档的"哈夫曼/线索/S020"在测试里替换为"红黑树/张三"
- **策略 B(扩展种子)**:按验收文档 §1 把 conftest 扩到 30 学生/6 知识点(哈夫曼/线索二叉树等)/S020 红色预警。工程量大,适合正式验收。

> 下文测试用例以**策略 A** 为基础给出输入输出(可直接跑通),策略 B 仅替换数据 ID。

### 5.2 L1 工具单测(直接调 `_t_xxx`,绕过 LLM)

照 `test_rag_exam_agent.py:38-251` 范式:用 `_ctx(session)` 构造 ToolContext,直接调 `_t_get_xxx(ctx, **args)`,断言返回结构。

#### TC-DIAG-TOOLS-T1: get_course_overview
- **输入**:`_t_get_course_overview(ctx, course_id=1)`
- **预期输出**:
  ```json
  {"course_id":1, "course_name":"数据结构", "student_count":3,
   "avg_score":<最近batch均分>, "pass_rate":<float>, "attendance_rate":<float>,
   "warning_count":1}
  ```
- **验收点**:✅ 字段齐全;✅ warning_count=1(张三预警);✅ student_count=3

#### TC-DIAG-TOOLS-T2: get_weak_knowledge_points
- **输入**:`_t_get_weak_knowledge_points(ctx, course_id=1, top_k=5)`
- **预期**:`weak_points` 按 accuracy 升序,红黑树(张三30%拉低班级均值)应靠前
- **验收点**:✅ 列表非空;✅ 含红黑树;✅ 按 accuracy 升序

#### TC-DIAG-TOOLS-T3: get_score_trend(班级)
- **输入**:`_t_get_score_trend(ctx, course_id=1, student_id=0)`
- **预期**:`{"scope":"class","trend":[{"assessment":"作业1","avg_score":..,"count":3},...]}` 三次批次
- **验收点**:✅ trend 长度=3;✅ scope=class

#### TC-DIAG-TOOLS-T4: get_score_trend(张三个人)
- **输入**:`_t_get_score_trend(ctx, course_id=1, student_id=1)`
- **预期**:`{"scope":"student","trend":[{"assessment":"作业1","score":85},{"assessment":"作业2","score":75},{"assessment":"期中","score":55}]}`
- **验收点**:✅ 下滑序列 85→75→55(对应 TC-DIAG-STUDENT-02 金标准)

#### TC-DIAG-TOOLS-T5: get_warning_students
- **输入**:`_t_get_warning_students(ctx, course_id=1)`
- **预期**:`{"warning_students":[{"student_id":1,"name":"张三","level":"中","reasons":["成绩下滑"]}]}`(level=2→中)
- **验收点**:✅ 含张三;✅ level 映射正确(2=中)

#### TC-DIAG-TOOLS-T6: get_student_detail(张三)
- **输入**:`_t_get_student_detail(ctx, course_id=1, student_id=1)`
- **预期**:含 scores(3次)、attendance_rate、weak_points(含红黑树)、strong_points、recent_answers
- **验收点**:✅ 字段齐全;✅ weak_points 含红黑树;✅ scores 下滑

#### TC-DIAG-TOOLS-T7: get_knowledge_mastery(张三)
- **输入**:`_t_get_knowledge_mastery(ctx, course_id=1, student_id=1)`
- **预期**:`points` 含红黑树 accuracy≈0.3 level=薄弱
- **验收点**:✅ 红黑树 low;✅ level 映射

#### TC-DIAG-TOOLS-T8: 工具失败兜底
- **输入**:`_t_get_student_detail(ctx, course_id=1, student_id=99999)`(不存在)
- **预期**:`{"error":"学生 99999 不存在"}`
- **验收点**:✅ 返回 error 字典,不抛异常(对应 SAFE-03 单工具失败不阻断)

### 5.3 L2 FC 循环集成测试(MockLLMProxy 脚本化)★核心

照 `test_rag_exam_agent.py:258-429` 范式:构造 `FCResult` 脚本序列 → `set_llm_proxy(MockLLMProxy(script))` → `run_agent(agent_type="diagnosis")` → 断言工具顺序+输出。

#### TC-DIAG-FC-01: 班级诊断工具调用顺序(对应 TC-DIAG-TOOLS-01)★关键
- **Mock 脚本**(5 步,前 4 步调工具,第 5 步输出 JSON):
  ```python
  script = [
    FCResult(content="", tool_calls=[{"id":"c1","name":"get_course_overview","arguments":{"course_id":1}}]),
    FCResult(content="", tool_calls=[{"id":"c2","name":"get_weak_knowledge_points","arguments":{"course_id":1}}]),
    FCResult(content="", tool_calls=[{"id":"c3","name":"get_warning_students","arguments":{"course_id":1}}]),
    FCResult(content="", tool_calls=[{"id":"c4","name":"get_score_trend","arguments":{"course_id":1}}]),
    FCResult(content=DIAG_JSON, tool_calls=[], finish_reason="stop"),
  ]
  ```
  其中 `DIAG_JSON` 是合法的诊断 JSON 字符串(含 scope/overall/findings/causes/suggestions/radar/meta)。
- **调用**:`run_agent(session_factory=sf, user_message="请对班级做全面学情诊断", user_id=1, course_id=1, agent_type="diagnosis", max_steps=8)`
- **预期**:
  - `result.error is None`
  - `tool_names = [tc.name for s in result.steps for tc in s.tool_calls]` 含上述 4 工具
  - `tool_names[0] == "get_course_overview"`(总览先行)
  - `len(result.steps) >= 5`
  - `result.answer == DIAG_JSON`(或包含之)
- **验收点**:✅ 总览最先;✅ 工具数≥4;✅ 覆盖成绩/知识点/预警

#### TC-DIAG-FC-02: 学生诊断调 get_student_detail(对应 TC-DIAG-TOOLS-02)
- **Mock 脚本**:首步 `tool_calls=[{name:"get_student_detail",arguments:{course_id:1,student_id:1}}]`
- **预期**:`tool_names` 含 `get_student_detail`;与班级诊断工具集不同
- **验收点**:✅ 调 get_student_detail;✅ 个人化

#### TC-DIAG-FC-03: 输出 JSON 结构完整性(对应 TC-DIAG-CLASS-01)
- **Mock 脚本**:1 步直接输出完整 JSON,`tool_calls=[]`
- **预期**:`json.loads(result.answer)` 含 6 顶层字段(scope/overall/findings/causes/suggestions/radar/meta);findings.strengths 与 risks 非空;suggestions≥1
- **验收点**:✅ 结构齐全

#### TC-DIAG-FC-04: 薄弱点识别(对应 TC-DIAG-CLASS-02,策略A)
- **Mock 脚本**:先调 get_weak_knowledge_points(真实返回含红黑树),再输出 JSON
- **预期**:输出 JSON 的 findings.risks 或 causes 命中"红黑树"
- **验收点**:✅ 命中预设薄弱点;✅ 不误报"二叉树"(张三 mastery=75,良好)

#### TC-DIAG-FC-05: 下滑学生识别(对应 TC-DIAG-STUDENT-02)
- **输入**:学生诊断 student_id=1(张三)
- **预期**:findings.risks 命中"成绩下滑"或"进步斜率负";归因提到态度或知识薄弱
- **验收点**:✅ 识别下滑(85→75→55)

#### TC-DIAG-FC-06: 稳定优秀无误报(对应 TC-DIAG-STUDENT-04)
- **输入**:学生诊断 student_id=3(王五,60→70→80 进步)
- **预期**:findings.risks 为空或低风险;strengths 非空
- **验收点**:✅ 不误报好学生

#### TC-DIAG-FC-07: 工具数不超 max_steps(对应 TC-DIAG-TOOLS-04)
- **输入**:max_steps=3,Mock 脚本一直调工具(不输出 content)
- **预期**:`result.truncated == True`;工具调用次数 ≤ 3;不发 content
- **验收点**:✅ 不超上限;✅ truncated 正确

#### TC-DIAG-FC-08: 单工具失败不阻断(对应 SAFE-03)
- **Mock 脚本**:调 `get_student_detail(student_id=99999)`(返回 error)→ 继续调其他工具 → 输出 JSON
- **预期**:`result.error is None`;某步 tool_result 含 error;最终仍有 JSON 输出
- **验收点**:✅ 单工具失败不阻断

#### TC-DIAG-FC-09: LLM 失败兜底(对应 SAFE-01)★关键
- **方法**:MockLLMProxy 抛 RuntimeError(模拟 8001 不可达)
- **预期**:`run_agent` 不抛异常;`result.error` 非空(或 truncated);前端侧降级为模板兜底(基于工具已拉的数据用规则生成)——⚠️ **现状 run_agent 在 LLM 失败时发 error 事件并返回,不会自动模板兜底**。模板兜底需在前端或后端包装层做:LLM 失败 → 用已调工具的结果 + `report_template.render_class_report` 生成降级报告
- **验收点**:✅ 不崩;✅ 仍有报告输出(需补兜底层,见 §6.1)

### 5.4 测试落地清单

- [ ] 决定种子策略(A 降级 / B 扩展),§5.1
- [ ] `tests/test_diagnosis_agent.py`:L1 工具单测 8 例(§5.2)
- [ ] L2 FC 循环集成 9 例(§5.3),照 `test_rag_exam_agent.py` 的 MockLLMProxy 范式
- [ ] LLM 失败兜底测试(FC-09),验证不崩
- [ ] 全绿后对照验收测试集 48 用例标 PASS/FAIL

---

## 6. 兜底与权限(对应 SAFE 用例)

### 6.1 兜底层级

| 失败点 | 兜底方式 | 验收用例 |
|---|---|---|
| LLM 不可达(8001 挂) | 后端发 error 事件;**前端/包装层**用已调工具结果 + `report_template.render_class_report` 生成模板降级报告 | SAFE-01 |
| LLM 输出非 JSON | 前端 JSON.parse 失败 → 纯文本展示 + "报告格式异常,可追问" | SAFE-02 |
| 单工具失败 | 工具返回 `{error}`,FC 循环继续;报告标注数据缺失 | SAFE-03 |
| truncated | done.answer 空 → "诊断未完成,可重试或缩小维度" | (SSE 链路) |
| 导出字段缺失 | `_diagnosis_to_report_fields` 用 `"-"` 兜底(`report.py:390` 模式) | EXPORT-04 |

> ⚠️ **SAFE-01 的模板兜底现状缺失**:`run_agent` 在 LLM 失败时只发 error、不自动生成模板报告。需在 DiagnosisView 前端 catch error 后,可选调一个轻量模板端点(或后端在 error 前尝试用工具结果生成降级 JSON)。建议后端在 `agent.py` diagnosis 分支加 try:调 LLM;except:用 `report_template` 兜底生成 JSON 塞进 content 事件。

### 6.2 权限层级(依赖 §3.3)

| 用例 | 拦截 | 预期 |
|---|---|---|
| SAFE-04 非授课教师 | 后端 `_check_course_access` | 403 |
| SAFE-05 学生 | 路由 `roles:['teacher']` + 后端角色校验 | 路由重定向 / 403 |
| SAFE-06 课程隔离 | ToolContext.course_id + 工具内过滤 | 只返本课程数据 |
| SAFE-07 重复点击 | 前端 running 锁 | 按钮 disabled |

### 6.3 联动闭环(对应 ACT/FLOW 用例)

| 动作 | 实现 | 跳转 |
|---|---|---|
| 生成练习(`toolHint=weakness_driven_quiz`) | `router.push('/quiz/manage', query:{knowledgePoints:...})` | AI 出题页,注入知识点 |
| 发通知(`toolHint=notify`) | 调 `sendWarningNotice(studentId)`(`api/analysis.ts`) | 预警通知 |
| 约谈(`toolHint=talk`) | `router.push('/analysis/warning', query:{studentId:...})` | 预警详情 |
| 生成干预任务 | 聚合 suggestions,按 toolHint 分别执行 | 任务清单 |
| 干预回流(FLOW-01) | 出题→答题→掌握度更新→再次诊断图论↑ | C1→A3 闭环 |

---

## 7. 联调与验收

### 7.1 联调顺序

1. 后端:diagnosis.py prompt + `_resolve_agent_setup` 分支 + 权限 + max_steps(§3.5)
2. 后端:MockLLMProxy 跑通 FC 循环(§5.3),验证工具顺序与 JSON 输出
3. 前端:菜单+路由+DiagnosisView 骨架(§4.1-4.2)
4. 前端:streamDiagnosis + DiagnosisProcess(§4.3-4.4),联调 SSE 流式
5. 前端:DiagnosisReport 班级版+学生版(§4.5.1)
6. 前端:异常链路(§4.5.2)
7. 后端:权限校验(§3.3),前端配合 403 处理(§4.5.3)
8. 导出适配层(§3.4)+ 导出按钮
9. 干预联动(§6.3)
10. 对照验收测试集 48 用例 + 2 演示场景全跑

### 7.2 验收红线(必须 100% 通过)

- 所有兜底用例(不崩):SAFE-01/02/03 + EXPORT-04
- 所有权限用例:SAFE-04/05/06(依赖 §3.3)
- TC-DIAG-DEMO-01(班级 8 步)+ TC-DIAG-DEMO-02(学生 4 步)
- 允许 ≤2 项 Major 不达标(如诊断耗时 35s 而非 30s)
- Minor 不阻断

### 7.3 风险与待确认

| 项 | 风险 | 处置 |
|---|---|---|
| LLM 输出 JSON 稳定性 | DeepSeek 偶发非 JSON | 前端兜底 + prompt 强约束 + 可选后端正则提取 ````json...```` |
| 诊断耗时 | 5-6 工具 + LLM 综合,可能 >30s | max_steps=8;概览深度只调 3 工具;前端骨架屏+过程可见缓解感知 |
| 会话记忆不存工具轨迹(D3) | 追问时 LLM 看不到上轮工具结果 | 追问允许重新调工具(ASK-02 正要求);预期校准见 §1.3 D3 |
| 种子数据缺口(D7) | 验收金标准与 conftest 不符 | 策略 A 降级 / 策略 B 扩展,§5.1 |
| 组卷工具对诊断可见 | diagnosis 挂了 `agent="both"`,8 个组卷工具也在 | MVP 不过滤(LLM 不会主动调);如需严格隔离,registry 加 category 过滤 |

---

## 8. 关键路径文件索引

| 文件 | 作用 | 改动 |
|---|---|---|
| `backend/app/services/agent/prompts/diagnosis.py` | 诊断 system prompt | 🔨 新建 |
| `backend/app/services/agent/prompts/__init__.py:7-9` | prompt 导出 | 🔨 加 diagnosis |
| `backend/app/services/agent/base.py:42-58` | `_resolve_agent_setup` | 🔨 加 diagnosis 分支 |
| `backend/app/api/v1/agent.py:37` | max_steps 上限 | 🔨 le=10 |
| `backend/app/api/v1/agent.py:55-126` | chat 端点 | 🔨 加 diagnosis 权限校验 |
| `backend/app/api/v1/analysis.py:103,180` | `_check_profile_access`/`_check_course_access` | 📎 复用 |
| `backend/app/api/v1/report.py:305-451` | 导出 + 适配层 | 🔨 加 `_diagnosis_to_report_fields` + report_type=5 |
| `backend/app/services/report_template.py` | 模板兜底 | 📎 复用(LLM 失败降级) |
| `backend/app/services/agent/tools/queries.py:673` | 10 个查询工具 | 📎 复用 |
| `backend/tests/conftest.py` | 种子数据 | 🔨 扩展或降级(§5.1) |
| `backend/tests/test_diagnosis_agent.py` | 诊断测试 | 🔨 新建(§5) |
| `frontend/src/config/menu.ts:38-49,138-194` | 菜单 | 🔨 3 处 |
| `frontend/src/router/index.ts:56-80` | 路由 | 🔨 加 diagnosis |
| `frontend/src/types/index.ts` | AgentType | 🔨 加 'diagnosis' |
| `frontend/src/api/agent.ts:61-67` | streamAgentChat | 🔨 加 maxSteps 参数 |
| `frontend/src/api/analysis.ts` | streamDiagnosis | 🔨 新增 |
| `frontend/src/views/analysis/DiagnosisView.vue` | 主视图 | 🔨 新建 |
| `frontend/src/components/analysis/DiagnosisProcess.vue` | 过程区 | 🔨 新建 |
| `frontend/src/components/analysis/DiagnosisReport.vue` | 报告区 | 🔨 新建 |
| `frontend/src/components/common/AnalysisFilterBar.vue` | 筛选栏 | 📎 复用 |
| `frontend/src/views/analysis/StudentProfileView.vue` | 布局范本 | 📎 参考 |
| `frontend/src/components/agent/AgentChat.vue:227-240` | 过程区渲染范本 | 📎 参考 |

---

*文档版本:v1.0 | 日期:2026-09-07 | 基于原型 v1.0 + 设计方案 v1.0 + 验收测试集 v1.0 + 代码探查*
