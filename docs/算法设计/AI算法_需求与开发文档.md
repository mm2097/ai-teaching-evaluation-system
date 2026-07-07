# AI 算法需求与开发文档

> 基于 AI 的数智化教学分析评价系统 —— 真 AI 部分的需求拆解与开发落地说明
>
> 文档版本：1.0 ｜ 日期：2026-07-07 ｜ 编写：思路全开队

---

## 0. 文档定位

本文档只覆盖系统中**真正依赖人工智能模型(LLM)** 的功能,即「生成式」部分。需求文档中其它「分析」类功能(学情画像、成绩趋势、知识点掌握度、异常预警、学习质量评价)本质是**统计 + 规则 + 加权计算**,属于确定性算法,不在本文档范围内,各自在对应的算法说明文档里展开。

**本文档面向的开发内容:**

| 编号 | 功能 | 是否真 AI | 算法类别 |
|------|------|----------|----------|
| A | AI 出题(基于知识点自动生成练习题) | ✅ 是 | LLM 生成 |
| B | 报告结论与教学建议生成 | ✅ 是(可选增强) | LLM 生成 |
| C | 客观题自动判分 | ❌ 否 | 规则匹配(配套说明) |

> 说明:C 本身不是 AI,但它和 A 强耦合(出题 → 作答 → 判分 → 回流掌握度),所以放在本文档里一起讲。

---

## 1. 需求来源

### 1.1 对应需求规格说明书条目

| 需求章节 | 条目编号 | 条目内容 | 本文档覆盖 |
|---------|---------|---------|-----------|
| 3.2.16 | AI.Exercise.Generate | 基于知识点 AI 自动生成练习题 | ✅ 主 |
| 3.2.16 | AI.Exercise.Manage | 教师预览、编辑、删除题目 | ✅(业务侧) |
| 3.2.16 | AI.Exercise.Publish | 发布、关闭答题任务 | ✅(业务侧) |
| 3.2.16 | AI.Exercise.Answer | 学生在线作答 | ✅(业务侧) |
| 3.2.16 | AI.Exercise.Judge | 客观题自动判分 | ✅ 规则 |
| 3.2.16 | AI.Exercise.Sync | 答题结果同步至知识点掌握度 | ✅(对接说明) |
| 3.2.15 | Report.Generate | 报告自动生成(结论/建议部分) | ✅ 可选 |

### 1.2 功能目标

1. **AI 出题**:任课教师选定课程、知识点范围、题型、数量、难度后,系统自动生成结构化练习题(题干 + 选项 + 答案 + 解析),教师审核后一键发布给班级。
2. **自动判分**:学生在线作答提交后,系统按题型规则即时判分,答题结果回流更新「知识点掌握度」统计。
3. **报告生成(可选)**:在学情报告里,基于已统计好的核心指标,用 LLM 生成自然语言的"分析结论"和"教学优化建议"段落。

---

## 2. AI 能力边界(重要)

明确**什么不是 AI**,避免设计走偏:

| 功能 | 性质 | 实现方式 |
|------|------|---------|
| 学情画像得分 | 数学 | 加权平均 |
| 成绩趋势/预测 | 数学 | 统计 + 趋势推算(线性回归属确定性公式) |
| 知识点掌握度 | 数学 | 正确率/失分率统计 |
| 异常学情预警 | 规则 | 阈值匹配(成绩下滑、缺勤超标、作业未交) |
| 学习质量综合评价 | 数学 | 预设权重加权求和 |
| 客观题判分 | 规则 | 答案字符串归一化比对 |
| **AI 出题** | **AI** | **LLM 生成** |
| **报告结论/建议** | **AI(可选)** | **LLM 生成** |

只有最后两行进入 AI 服务。

---

## 3. 总体架构

### 3.1 分层

```
┌─────────────────────────────────────────────────┐
│  前端 (Vue 3)                                    │
│  教师出题页 / 学生答题页 / 报告预览页              │
└────────────────────┬────────────────────────────┘
                     │ HTTP/JSON
┌────────────────────▼────────────────────────────┐
│  后端业务服务 (FastAPI)                          │
│  ├─ api/v1/exercises.py    题目管理、答题、判分  │
│  ├─ api/v1/ai.py           AI 调用入口(薄封装)  │
│  ├─ models/                SQLModel 数据模型     │
│  └─ services/              业务编排              │
└──────────┬──────────────────────┬───────────────┘
           │ 内部 HTTP              │ 直连
┌──────────▼─────────┐   ┌─────────▼──────────────┐
│  AI 服务 (Python)   │   │  LLM API               │
│  ├─ generator.py    │   │  (DeepSeek / 通义 /     │
│  │   出题 prompt    │   │   智谱 GLM / OpenAI)    │
│  ├─ reporter.py     │   │                        │
│  │   报告 prompt    │   │                        │
│  └─ schemas.py      │   │                        │
│      结构校验       │   │                        │
└─────────────────────┘   └────────────────────────┘
           │
┌──────────▼──────────────────────────────────────┐
│  数据库 (SQLite,可平滑切 PostgreSQL/MySQL)      │
│  题目、答题记录、知识点                          │
└─────────────────────────────────────────────────┘
```

### 3.2 设计原则

1. **AI 服务薄而专**:只负责 prompt 拼装、模型调用、输出结构化校验;不碰数据库、不碰鉴权。业务编排全部在后端 FastAPI 侧。
2. **可降级**:LLM 调用失败/超时时,返回明确错误,绝不允许生成残缺题目入库。
3. **可替换**:LLM 厂商通过环境变量切换,prompt 与厂商解耦。
4. **强校验**:LLM 输出必须通过 JSON Schema 校验后才算成功;不通过则重试或报错。
5. **可追溯**:每次生成都记录 prompt 摘要、模型版本、耗时、token 用量,便于回溯。

---

## 4. AI 出题算法(核心)

### 4.1 输入

```json
{
  "course_id": 1,
  "knowledge_points": ["二叉树遍历", "哈希表"],
  "question_types": ["single_choice", "multi_choice", "judge"],
  "count": 10,
  "difficulty": "medium",          // easy / medium / hard
  "extra_requirements": "面向初学者,干扰项要合理"  // 可选
}
```

### 4.2 输出(结构化题目列表)

```json
{
  "questions": [
    {
      "type": "single_choice",
      "knowledge_point": "二叉树遍历",
      "difficulty": "medium",
      "stem": "对二叉搜索树进行中序遍历,得到的序列是……",
      "options": [
        {"key": "A", "text": "递增有序序列"},
        {"key": "B", "text": "递减有序序列"},
        {"key": "C", "text": "无序序列"},
        {"key": "D", "text": "只包含叶子结点"}
      ],
      "answer": "A",
      "explanation": "二叉搜索树的中序遍历满足左<根<右,因此结果递增有序。"
    }
  ]
}
```

### 4.3 题型与判分规则对应

| 题型 | 字段 | 答案格式 | 判分方式 |
|------|------|---------|---------|
| 单选 single_choice | options(4 个)、answer | "A" / "B" / "C" / "D" | 字符串等值 |
| 多选 multi_choice | options(4 个)、answer | "ABD"(字母升序拼接) | 集合相等(顺序无关) |
| 判断 judge | 无 options、answer | true / false | 布尔等值 |
| 填空 fill_blank | answer 接受多个等价答案 | ["链表", "linked list"] | 命中任一即对(可做大小写/去空格归一化) |

### 4.4 LLM 选型

**推荐方案(国内可用、便宜、质量稳定):**

| 优先级 | 厂商 / 模型 | 优点 | 接入方式 |
|--------|------------|------|---------|
| 主选 | **DeepSeek**(deepseek-chat) | 价格极低、中文好、JSON 输出稳定 | OpenAI 兼容 SDK |
| 备选 | 通义千问(qwen-plus / qwen-turbo) | 阿里云生态、有免费额度 | DashScope SDK |
| 备选 | 智谱 GLM(gl-4-flash) | 免费额度充足,适合课程项目 | zhipuai SDK |
| 备选 | OpenAI(gpt-4o-mini) | 质量高,但访问/付费受限 | openai SDK |

> 三家国内厂商都兼容 OpenAI SDK 的请求格式,切换只需改 `base_url` 和 `api_key`,代码改动量极小。

**统一封装**:在 `algorithm/src/llm_client.py` 里做一层 `chat_completion(messages, response_format="json")` 抽象,业务层不感知具体厂商。

### 4.5 Prompt 设计

采用 **系统指令 + JSON Schema 约束 + Few-shot 示例** 三段式:

```
[SYSTEM]
你是一名计算机学院的命题专家。根据给定的知识点和题型,生成符合教学大纲的练习题。
你必须严格输出 JSON,结构如下:
{
  "questions": [
    {"type":"single_choice","knowledge_point":"...","difficulty":"...",
     "stem":"...","options":[{"key":"A","text":"..."},...],
     "answer":"A","explanation":"..."}
  ]
}
要求:
1. 题干准确无歧义,选项中必须包含 1 个正确答案和 3 个有迷惑性的错误选项。
2. 干扰项要 plausible,不能有明显荒谬选项。
3. 解析简明扼要,说明正确答案的依据。
4. 不同题目之间不得重复。
5. 难度分布:简单 30% / 中等 50% / 困难 20%(可在用户指定难度内浮动)。

[USER]
课程:数据结构与算法
知识点:二叉树遍历、哈希表
题型:单选题 6 道、判断题 2 道、多选题 2 道
难度:medium
其它要求:面向初学者,干扰项要合理

请输出 10 道题的 JSON。
```

**关键技巧:**

- 启用 **JSON 模式 / Structured Output**(`response_format={"type":"json_object"}`),让模型直接吐 JSON。
- 给 **1~2 个 few-shot 示例**,显著降低格式错误率。
- **温度 temperature=0.7**:兼顾多样性和稳定性。
- 限制 `max_tokens`,防止失控。

### 4.6 生成主流程

```
[教师点击"生成题目"]
        │
        ▼
[后端 POST /api/v1/ai/exercises/generate]
        │
        ├─ 1. 参数校验(知识点存在?题型合法?数量 1~30?)
        ├─ 2. 拉取知识点名称、课程名称
        ├─ 3. 拼装 prompt
        ├─ 4. 调用 AI 服务 → LLM
        │
        ▼
[AI 服务]
        ├─ 5. LLM 生成(JSON 模式)
        ├─ 6. JSON 解析 + Schema 校验
        │     ├─ 失败 → 重试(最多 2 次)→ 仍失败则返回错误
        │     └─ 成功 ↓
        ├─ 7. 业务校验:答案在选项范围内、题干不重复、知识点匹配
        ├─ 8. 返回结构化题目列表
        │
        ▼
[后端]
        ├─ 9. 题目以"草稿"状态暂存(draft,未发布)
        └─ 10. 返回前端供教师预览编辑
        │
        ▼
[教师审核 → 发布]
        └─ 状态 draft → published,对学生可见
```

### 4.7 质量保障与降级

| 异常 | 处理 |
|------|------|
| LLM 超时(>30s) | 重试 1 次,仍失败返回 503,提示教师稍后再试 |
| JSON 解析失败 | 提取 ```json``` 代码块二次解析,失败则重试 |
| Schema 校验失败(字段缺失/类型错) | 重试 2 次,仍失败丢弃该批 |
| 选项答案不在 A-D 范围 | 自动修正或丢弃该题 |
| 题干重复(同批次内) | 去重 |
| 知识点漂移(生成的题不属于指定知识点) | 保留但标注"待人工确认" |
| 模型返回题目数 < 请求数 | 补一轮生成或如实返回 |

---

## 5. 客观题判分算法(规则,非 AI)

判分不需要 LLM,放在后端 `services/judge.py`:

```python
def judge(question, student_answer):
    if question.type == "single_choice":
        return student_answer.strip().upper() == question.answer.upper()

    if question.type == "multi_choice":
        # 集合相等,顺序无关
        return set(student_answer.upper()) == set(question.answer.upper())

    if question.type == "judge":
        return bool(student_answer) == bool(question.answer)

    if question.type == "fill_blank":
        norm = lambda s: s.strip().lower()
        acceptable = [norm(a) for a in question.answer_list]
        return norm(student_answer) in acceptable

    raise ValueError(f"未知题型: {question.type}")
```

**答案归一化规则:**

- 字母统一大写
- 去除前后空格
- 填空题忽略大小写差异
- 多选题按集合比较,不关心顺序

判分完成后,**异步回流** 到知识点掌握度统计:

```
答题记录入库 → 触发知识点正确率重算 → 更新 knowledge_mastery 表
```

(掌握度本身是统计值,不是 AI。)

---

## 6. 报告结论与建议生成(可选增强)

### 6.1 定位

报告里的"核心指标"由后端统计生成(数学),"**分析结论 + 教学优化建议**"两段自然语言文字由 LLM 生成,让报告更可读。

### 6.2 输入(LLM 不直接看原始数据,只看统计摘要)

```json
{
  "course": "数据结构与算法",
  "class_size": 45,
  "metrics": {
    "avg_score": 76.2,
    "pass_rate": 0.82,
    "attendance_rate": 0.91,
    "warning_count": 6
  },
  "weak_knowledge_points": [
    {"name": "红黑树", "correct_rate": 0.42},
    {"name": "动态规划", "correct_rate": 0.51}
  ],
  "trend": "近三次作业平均分:78 → 74 → 71,呈下滑趋势"
}
```

### 6.3 Prompt

```
[SYSTEM]
你是教学分析助手。基于课程统计数据,用专业、简练的中文输出两段文字:
1. 「分析结论」:2~3 句,点明班级学习状态、关键问题。
2. 「教学建议」:3 条可执行的改进措施,每条不超过 30 字。
严格输出 JSON:{"conclusion":"...","suggestions":["...","...","..."]}
不要编造未提供的数据。

[USER]
{上面的统计摘要 JSON}
```

### 6.4 输出处理

- Schema 校验 → 写入报告 `conclusion` / `suggestions` 字段。
- 即使 LLM 失败,报告仍能生成(结论/建议为空或用模板兜底),不影响核心指标展示。

---

## 7. 接口设计

### 7.1 AI 出题

```
POST /api/v1/ai/exercises/generate
Authorization: Bearer <teacher_token>

Request:
{
  "course_id": 1,
  "knowledge_points": ["二叉树遍历"],
  "question_types": ["single_choice", "judge"],
  "count": 5,
  "difficulty": "medium",
  "extra_requirements": ""
}

Response 200:
{
  "batch_id": 123,
  "questions": [ ... ],
  "meta": {"model": "deepseek-chat", "elapsed_ms": 4200, "tokens": 1820}
}

Response 503:
{"detail": "AI 服务暂不可用,请稍后重试"}
```

### 7.2 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/exercises?course_id=&status=` | 查询题目列表(草稿/已发布) |
| PUT | `/api/v1/exercises/{id}` | 教师编辑单题 |
| DELETE | `/api/v1/exercises/{id}` | 删除 |
| POST | `/api/v1/exercises/publish` | 批量发布:`{exercise_ids:[]}` |

### 7.3 学生答题

```
POST /api/v1/exercises/{id}/answer
Authorization: Bearer <student_token>

Request:
{"answer": "A"}          # 或 "ABD" / true / "链表"

Response 200:
{"correct": true, "score": 5, "knowledge_mastery_updated": true}
```

### 7.4 报告生成(可选)

```
POST /api/v1/ai/report/generate
Request: {"course_id": 1, "scope": "class"}
Response 200:
{
  "metrics": {...},                    # 后端统计
  "conclusion": "...",                 # LLM 生成
  "suggestions": ["...", "...", "..."] # LLM 生成
}
```

---

## 8. 数据模型(SQLModel)

### 8.1 知识点表 KnowledgePoint

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| course_id | int FK | 所属课程 |
| name | str | 知识点名称 |
| parent_id | int? | 父知识点(知识树) |

### 8.2 题目表 Exercise

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| course_id | int FK | |
| knowledge_point_id | int FK | |
| type | str | single_choice / multi_choice / judge / fill_blank |
| difficulty | str | easy / medium / hard |
| stem | text | 题干 |
| options | json | 选项(选择题) |
| answer | str | 标准答案 |
| answer_list | json | 填空题等价答案列表 |
| explanation | text | 解析 |
| status | str | draft / published / closed |
| source | str | ai / manual |
| batch_id | int? | AI 生成批次 |
| created_by | int FK | 教师 |
| created_at | datetime | |

### 8.3 答题记录表 AnswerRecord

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| exercise_id | int FK | |
| student_id | int FK | |
| answer | str | 学生作答 |
| is_correct | bool | 判分结果 |
| score | float | 得分 |
| answered_at | datetime | |

### 8.4 AI 调用日志 AiCallLog(可追溯)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| batch_id | int | 生成批次 |
| scene | str | generate_exercise / generate_report |
| model | str | 模型名 |
| prompt_hash | str | prompt 摘要 |
| input_tokens | int | |
| output_tokens | int | |
| elapsed_ms | int | |
| success | bool | |
| created_at | datetime | |

---

## 9. 开发任务分解

| 任务 | 位置 | 工时估计 | 依赖 |
|------|------|---------|------|
| LLM 客户端封装(多厂商) | `algorithm/src/llm_client.py` | 0.5 天 | 选型确定 |
| 出题 prompt 模板 + JSON Schema | `algorithm/src/prompts/exercise.py` | 0.5 天 | — |
| 出题生成服务 | `algorithm/src/generator.py` | 1 天 | 上 2 项 |
| 报告生成服务 | `algorithm/src/reporter.py` | 0.5 天 | LLM 客户端 |
| AI 服务 HTTP 入口(FastAPI) | `algorithm/src/main.py` | 0.5 天 | 上 2 项 |
| 后端 AI 薄封装接口 | `backend/app/api/v1/ai.py` | 0.5 天 | AI 服务 |
| 数据模型(Exercise / AnswerRecord) | `backend/app/models/` | 0.5 天 | — |
| 题目管理 CRUD 接口 | `backend/app/api/v1/exercises.py` | 1 天 | 模型 |
| 判分服务 | `backend/app/services/judge.py` | 0.5 天 | 模型 |
| 答题回流掌握度 | `backend/app/services/mastery.py` | 0.5 天 | 判分 |
| 教师出题页前端 | `frontend/src/views/teacher/` | 1.5 天 | 接口 |
| 学生答题页前端 | `frontend/src/views/student/` | 1 天 | 接口 |
| 测试(单元 + 联调) | 各模块 | 1.5 天 | — |
| **合计** | | **≈ 10 天/人** | |

---

## 10. 配置与部署

### 10.1 环境变量(后端 `backend/.env` 新增)

```bash
# AI 服务地址(默认本地起在 8001)
AI_SERVICE_URL=http://127.0.0.1:8001

# LLM 配置
LLM_PROVIDER=deepseek                  # deepseek / qwen / zhipu / openai
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=30
LLM_MAX_RETRY=2
```

### 10.2 依赖新增

`algorithm/requirements.txt`:

```
fastapi
uvicorn[standard]
openai          # 兼容多家厂商
pydantic
loguru
```

### 10.3 启动 AI 服务

```bash
cd algorithm
pip install -r requirements.txt
uvicorn src.main:app --port 8001 --reload
```

### 10.4 联调清单

- [ ] 后端能调通 AI 服务 `/generate_exercises`
- [ ] AI 服务能调通 LLM 厂商(用真实 key 验证一次)
- [ ] 生成结果能入库(草稿态)
- [ ] 教师能编辑发布
- [ ] 学生能答题
- [ ] 判分正确,掌握度有更新
- [ ] LLM 失败时前端有友好提示

---

## 11. 验收标准

1. **出题正确率**:抽测 3 门课 × 10 题,JSON 格式正确率 100%,知识点匹配率 ≥ 90%,无明显错题(答案错位、选项重复等)。
2. **稳定性**:连续生成 20 次,成功率 ≥ 95%(失败均为可恢复错误并提示)。
3. **性能**:单次 10 题生成 ≤ 15 秒。
4. **判分**:4 种题型全覆盖,正确率 100%(用例驱动)。
5. **降级**:LLM 不可用时,系统其它功能不受影响。
6. **可追溯**:`AiCallLog` 完整记录,可按批次/时间查询。

---

## 12. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 厂商服务波动 | 双厂商配置,主备可切;增加重试 |
| 生成题目质量参差 | 教师审核环节不可省,草稿态不入课堂 |
| 成本超支 | 预算告警;选用便宜模型(DeepSeek/Flash);缓存常见知识点题库 |
| 学术诚信 | 题目入库前去重;每学期补充新题 |
| 数据隐私 | 出题 prompt 不带学生姓名/学号,只带知识点 |
| prompt 注入 | 用户输入的 extra_requirements 做长度限制 + 字符过滤 |

---

## 附录:目录结构

```
algorithm/
├── requirements.txt
└── src/
    ├── __init__.py
    ├── main.py              # FastAPI 入口
    ├── llm_client.py        # 多厂商 LLM 封装
    ├── generator.py         # 出题主逻辑
    ├── reporter.py          # 报告生成
    ├── judge.py             # (可选)判分纯函数,后端也可直接实现
    ├── schemas.py           # Pydantic 输入输出模型
    └── prompts/
        ├── exercise.py      # 出题 prompt 模板
        └── report.py        # 报告 prompt 模板
```
