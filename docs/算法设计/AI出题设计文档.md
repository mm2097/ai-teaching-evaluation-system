# AI 出题设计文档

> 基于 AI 的数智化教学分析评价系统 —— AI 出题与在线答题模块的详细设计
>
> 文档版本：1.0 ｜ 日期：2026-07-08 ｜ 编写：思路全开队
>
> 关联文档：`AI算法_需求与开发文档.md`、`算法决策记录.md`（D09/D10/D12/D13）、需求规格说明书 v2.0 第 3.2.16 节

---

## 0. 文档定位

本文档专门覆盖**需求 3.2.16「AI 出题与在线答题」** 的完整设计，包括功能亮点、业务流程、数据模型、LLM 调用、判分算法、接口契约、前端交互与质量保障。是该模块开发的唯一依据。

`AI算法_需求与开发文档.md` 是本文档的上位总览，本文档在其基础上细化并扩展。

---

## 1. 功能定位

### 1.1 一句话定位

任课教师选定课程、知识点范围、题型、数量、难度后，系统基于 LLM 自动生成结构化练习题，教师审核后发布给班级，学生在线作答，系统自动判分并把结果回流到知识点掌握度。

### 1.2 核心价值

| 痛点 | 本模块的解法 |
|------|------------|
| 教师命题耗时 | AI 一次生成 10 题仅需 10-15 秒，且支持批量 |
| 题库陈旧、重复 | 每次生成都是新的，配合 TF-IDF 去重避免与已有题重复 |
| 判分工作量大 | 客观题全部自动判分，4 种题型覆盖 |
| 答题数据散落 | 答题结果自动回流知识点掌握度，形成数据闭环 |
| 错题进课堂 | 三态流（草稿→审核→发布），教师把关 |

---

## 2. 功能亮点

> 这一节是差异化竞争力，验收/答辩重点讲。

### 亮点 1：知识图谱驱动的精准出题

不只是"按知识点出题"，而是**基于班级知识点掌握度数据（3.2.10 分析结果）驱动**：

- 教师进入出题页，系统自动展示"班级薄弱知识点 Top5"；
- 教师一键勾选薄弱点，AI 自动针对薄弱点出题；
- 生成时 prompt 注入每个薄弱点的班级平均正确率，让题目难度适配；
- 解决"出的题学生早会了，不会的没练到"的问题。

### 亮点 2：真题级 Few-shot 引导，质量接近人工

项目已配备 2023-2025 年 408 统考真题、计算机网络题库（见 `docs/测试数据及模板`）。将这些真题作为 few-shot 示例注入 prompt：

- LLM 学到的命题风格、选项迷惑性、解析写法都是真题级；
- 相比"凭空生成"，题目严谨度和区分度显著提升；
- 不同课程可配置不同的 few-shot 题库。

### 亮点 3：三道质量防线，杜绝错题进课堂

| 防线 | 机制 | 作用 |
|------|------|------|
| 第一道 | JSON Schema + Pydantic 强校验 | 字段缺失、类型错、选项数不对 → 自动丢弃 |
| 第二道 | 业务规则校验 | 答案不在选项范围、选项重复、题干重复 → 自动修正或剔除 |
| 第三道 | 教师人工审核（草稿态） | AI 生成的题一律进草稿，教师审核后才发布 |

三道防线后，错的题进不了学生视野。

### 亮点 4：四题型全覆盖 + 答案归一化判分

支持**单选、多选、判断、填空**四种题型，每种都有标准化的判分规则：

| 题型 | 答案格式 | 判分规则 |
|------|---------|---------|
| 单选 | "A" / "B" / "C" / "D" | 字符串等值（大小写归一） |
| 多选 | "ABD"（字母升序拼接） | **集合相等**，顺序无关 |
| 判断 | true / false | 布尔等值 |
| 填空 | ["链表", "linked list"]（多等价答案） | 命中任一即对，大小写/去空格归一 |

判分是纯函数（规则匹配，非 LLM），可单测、可回归、零幻觉。

### 亮点 5：答题数据闭环回流掌握度

答题结束 ≠ 数据结束。判分完成后异步触发知识点掌握度重算：

```
学生提交答案 → 自动判分 → 写入 AnswerRecord → 异步触发 → 更新 KnowledgeMastery 表
                                                            ↓
                                            知识点热力图（3.2.10）实时刷新
```

学生每做一次 AI 出题，班级知识点热力图就更新一次，形成"出题→答题→分析→再出题"的闭环。

### 亮点 6：批次全链路可追溯

每次生成都记录 `AiCallLog`：

- prompt 摘要（hash）、模型版本、输入输出 token、耗时、成功/失败；
- 题目带 `batch_id`，可按批次查询、对比、复用；
- 教师可看到"这次生成的 10 题质量怎么样"，决定保留或重生成。

### 亮点 7：难度梯度自适应

教师在 prompt 里指定难度（easy/medium/hard），系统按"简单 30% / 中等 50% / 困难 20%"分布生成，符合教育测量学的题目难度分布惯例，而非全部中等。

### 亮点 8：LLM 失败优雅降级

- LLM 超时/限流 → 重试 2 次 → 仍失败返回 503，**绝不入库残缺题目**；
- JSON 解析失败 → 提取 ```json``` 代码块二次解析；
- Schema 校验失败 → 丢弃单题，保留合格题目；
- 整体失败 → 前端友好提示"AI 服务繁忙，请稍后重试"，不影响系统其他功能。

### 亮点 9：题目去重，避免题库冗余

每次新生成的题，与该课程已有题库做 TF-IDF 余弦相似度检查（决策 D12）：

- 相似度 ≥ 0.8 → 自动剔除并补题；
- 相似度 0.6-0.8 → 标注"疑似重复"，教师审核时高亮；
- 相似度 < 0.6 → 正常入库。

### 亮点 10：教师二次编辑 + 解析自动生成

- AI 生成的题目，教师可全字段编辑（题干、选项、答案、解析、难度）；
- 每题自动附带解析（LLM 生成），学生答题后可见，相当于"自动讲解"；
- 教师可批量发布/取消发布。

---

## 3. 业务流程设计

### 3.1 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│  教师侧                                                      │
│                                                              │
│  ① 选择课程 + 知识点范围 + 题型 + 数量 + 难度               │
│       │                                                      │
│       │ (可选) 系统推荐班级薄弱知识点                        │
│       ▼                                                      │
│  ② 点击「AI 生成」                                          │
│       │                                                      │
└───────┼──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  后端业务层 (FastAPI)                                        │
│                                                              │
│  ③ 参数校验（知识点存在、题型合法、数量 1-30、权限）        │
│  ④ 拉取课程名、知识点名、薄弱点掌握度                       │
│  ⑤ 拼装 prompt（系统指令 + few-shot + 用户需求）            │
│  ⑥ 调用 AI 服务 (HTTP → algorithm:8001)                     │
└───────┬──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  AI 服务 (Python/FastAPI, 8001)                              │
│                                                              │
│  ⑦ 调通义千问 qwen-plus（JSON 模式）                        │
│  ⑧ JSON 解析（失败则提取代码块二次解析）                    │
│  ⑨ Pydantic Schema 强校验                                   │
│  ⑩ 业务校验：答案合法、选项不重复、题干不重复               │
│  ⑪ 写 AiCallLog（模型/token/耗时/成功）                     │
│  ⑫ 返回结构化题目列表                                       │
└───────┬──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  后端业务层                                                  │
│                                                              │
│  ⑬ TF-IDF 去重（与已有题库比）                              │
│  ⑭ 题目以 draft 状态入库，带 batch_id                       │
│  ⑮ 返回前端供教师预览                                       │
└───────┬──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  教师审核                                                    │
│                                                              │
│  ⑯ 预览题目（疑似重复高亮、可编辑、可删除）                │
│  ⑰ 编辑 → 保存 / 删除 / 全选发布                            │
│  ⑱ 状态：draft → published                                  │
└───────┬──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  学生侧                                                      │
│                                                              │
│  ⑲ 进入答题中心，看到已发布任务                             │
│  ⑳ 在线作答（单题或整卷模式）                               │
│  ㉑ 提交答案                                                │
└───────┬──────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  自动判分 + 数据回流                                         │
│                                                              │
│  ㉒ 按题型规则判分（纯函数）                                │
│  ㉓ 写入 AnswerRecord                                       │
│  ㉔ 异步触发 KnowledgeMastery 重算（3.2.10）                │
│  ㉕ 返回结果（正确性、得分、解析）                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 状态机

题目状态：

```
draft（草稿）──教师发布──► published（已发布）──教师关闭──► closed（已关闭）
     │                         │
     │教师删除                 │教师删除
     ▼                         ▼
  deleted                    deleted
```

答题任务状态（独立于题目）：

```
pending（未开始）──学生进入──► in_progress（答题中）──提交──► submitted（已提交）
```

---

## 4. 数据模型设计

### 4.1 知识点表 KnowledgePoint

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| course_id | int FK | 所属课程 |
| name | str | 知识点名称 |
| parent_id | int? | 父知识点（构建知识树） |
| description | str | 知识点描述（辅助 LLM 出题） |

### 4.2 题目表 Exercise

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| course_id | int FK | 所属课程 |
| knowledge_point_id | int FK | 主知识点 |
| type | str | single_choice / multi_choice / judge / fill_blank |
| difficulty | str | easy / medium / hard |
| stem | text | 题干 |
| options | json | 选项（选择题），格式 `[{"key":"A","text":"..."}]` |
| answer | str | 标准答案 |
| answer_list | json | 填空题等价答案列表 |
| explanation | text | 解析（学生答题后可见） |
| status | str | draft / published / closed / deleted |
| source | str | ai / manual |
| batch_id | int? | AI 生成批次号 |
| similarity_flag | bool | 疑似重复标记（TF-IDF 0.6-0.8） |
| created_by | int FK | 教师 |
| created_at | datetime | |

### 4.3 答题任务表 ExerciseTask

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| course_id | int FK | |
| title | str | 任务标题（如"红黑树专题练习"） |
| teacher_id | int FK | |
| exercise_ids | json | 包含的题目 ID 列表 |
| class_id | int FK | 发布班级 |
| status | str | published / closed |
| deadline | datetime? | 截止时间（可选） |
| created_at | datetime | |

### 4.4 答题记录表 AnswerRecord

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| exercise_id | int FK | |
| task_id | int FK | 所属任务 |
| student_id | int FK | |
| answer | str | 学生作答 |
| is_correct | bool | 判分结果 |
| score | float | 得分 |
| answered_at | datetime | |

### 4.5 AI 调用日志 AiCallLog

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| batch_id | int | 生成批次号 |
| scene | str | generate_exercise / generate_report |
| model | str | 模型名（qwen-plus） |
| prompt_hash | str | prompt 摘要 hash |
| input_tokens | int | |
| output_tokens | int | |
| elapsed_ms | int | |
| success | bool | |
| error_msg | str? | 失败原因 |
| created_at | datetime | |

---

## 5. LLM 调用设计

### 5.1 厂商与模型（决策 D13）

- **主选**：通义千问 `qwen-plus`（团队持有可用 API Key）
- **接入方式**：DashScope OpenAI 兼容模式
- **备选**：智谱 GLM-4-Flash、DeepSeek（切换仅需改环境变量）
- **统一封装**：`algorithm/src/llm_client.py` 的 `chat_completion()`

```bash
LLM_PROVIDER=qwen
LLM_API_KEY=<团队 Key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_TIMEOUT=30
LLM_MAX_RETRY=2
LLM_TEMPERATURE=0.7
```

### 5.2 Prompt 三段式设计

```
[SYSTEM] 命题专家人设 + 输出 JSON Schema + 铁律
[FEW-SHOT] 2 道真题示例（从 docs/测试数据及模板 的 408 真题里选）
[USER] 课程 / 知识点 / 题型分布 / 数量 / 难度 / 薄弱点数据 / 额外要求
```

**系统指令（精简版）**：

```
你是一名计算机学院的命题专家。根据给定的知识点和题型，生成符合教学大纲的练习题。
你必须严格输出 JSON，结构如下：
{
  "questions": [
    {"type":"single_choice","knowledge_point":"...","difficulty":"...",
     "stem":"...","options":[{"key":"A","text":"..."}],
     "answer":"A","explanation":"..."}
  ]
}

铁律：
1. 题干准确无歧义，选项包含 1 个正确答案和 3 个有迷惑性的错误选项。
2. 干扰项要 plausible，不能有明显荒谬选项。
3. 解析简明扼要，说明正确答案的依据。
4. 不同题目之间不得重复。
5. 难度分布：简单 30% / 中等 50% / 困难 20%。
6. 严格按用户指定的知识点出题，不得超出范围。
```

**用户指令模板**：

```
课程：{course_name}
知识点：{knowledge_points}
题型分布：单选 {n1} 道 / 多选 {n2} 道 / 判断 {n3} 道 / 填空 {n4} 道
难度：{difficulty}
班级掌握度参考（用于校准难度）：
  - {kp1}: 正确率 {rate1}%
  - {kp2}: 正确率 {rate2}%
其它要求：{extra_requirements}

请输出 {total} 道题的 JSON。
```

### 5.3 关键技巧

| 技巧 | 配置 | 作用 |
|------|------|------|
| JSON 模式 | `response_format={"type":"json_object"}` | 强制 JSON 输出 |
| Few-shot | 2 道真题示例 | 命题风格接近真题 |
| 温度 | 0.7 | 兼顾多样性和稳定性 |
| max_tokens | 限制（如 4000） | 防失控 |
| 重试 | 最多 2 次 | 应对偶发失败 |

### 5.4 输出校验三道防线（亮点 3）

```python
# 防线 1：JSON 解析（含代码块二次解析）
try:
    data = json.loads(raw_text)
except JSONDecodeError:
    # 提取 ```json ... ``` 代码块重试
    match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    data = json.loads(match.group(1))

# 防线 2：Pydantic Schema 强校验
class QuestionSchema(BaseModel):
    type: Literal["single_choice","multi_choice","judge","fill_blank"]
    knowledge_point: str
    difficulty: Literal["easy","medium","hard"]
    stem: str
    options: list[Option] | None
    answer: str
    explanation: str

# 防线 3：业务规则校验
for q in questions:
    assert q.answer in valid_answer_range(q)        # 答案在选项范围内
    assert len({o.text for o in q.options}) == 4    # 选项文本不重复
    assert q.knowledge_point in required_kps         # 知识点未漂移
```

### 5.5 降级策略

| 异常 | 处理 |
|------|------|
| LLM 超时（>30s） | 重试 1 次，仍失败返回 503 |
| JSON 解析失败 | 提取 ```json``` 代码块二次解析，失败则重试 |
| Schema 校验失败 | 重试 2 次，仍失败丢弃该批 |
| 答案不在选项范围 | 自动修正或丢弃该题 |
| 题干重复（同批次内） | 去重 |
| 知识点漂移 | 保留但标注"待人工确认" |
| 返回题数 < 请求数 | 补一轮生成或如实返回 |

---

## 6. 判分算法设计

判分是纯函数（规则匹配，非 LLM），位置：`backend/app/services/judge.py`。

```python
def judge(question: Exercise, student_answer: str) -> tuple[bool, float]:
    """判分纯函数，返回 (是否正确, 得分)。"""

    if question.type == "single_choice":
        correct = student_answer.strip().upper() == question.answer.upper()
        return correct, 5.0 if correct else 0.0

    if question.type == "multi_choice":
        # 集合相等，顺序无关
        correct = set(student_answer.upper()) == set(question.answer.upper())
        return correct, 8.0 if correct else 0.0

    if question.type == "judge":
        correct = _to_bool(student_answer) == _to_bool(question.answer)
        return correct, 5.0 if correct else 0.0

    if question.type == "fill_blank":
        norm = lambda s: s.strip().lower()
        acceptable = [norm(a) for a in question.answer_list]
        correct = norm(student_answer) in acceptable
        return correct, 5.0 if correct else 0.0

    raise ValueError(f"未知题型: {question.type}")


def _to_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "t", "对", "正确", "1")
```

**答案归一化规则**：
- 字母统一大写
- 去除前后空格
- 填空题忽略大小写
- 多选题按集合比较，不关心顺序

**掌握度回流**（判分后异步触发）：

```python
async def sync_mastery(answer: AnswerRecord):
    """判分完成后异步更新知识点掌握度。"""
    kp_id = answer.exercise.knowledge_point_id
    # 重算该学生在该知识点的历史正确率
    records = await get_records(answer.student_id, kp_id)
    correct_rate = sum(r.is_correct for r in records) / len(records)
    await update_knowledge_mastery(
        student_id=answer.student_id,
        knowledge_point_id=kp_id,
        correct_rate=correct_rate,
    )
```

---

## 7. 接口设计

### 7.1 AI 出题（核心）

```
POST /api/v1/ai/exercises/generate
Authorization: Bearer <teacher_token>

Request:
{
  "course_id": 1,
  "knowledge_points": ["二叉树遍历", "红黑树"],
  "question_types": {"single_choice": 6, "multi_choice": 2, "judge": 2},
  "difficulty": "medium",
  "extra_requirements": "面向初学者，干扰项要合理"
}

Response 200:
{
  "batch_id": 123,
  "questions": [...],
  "meta": {
    "model": "qwen-plus",
    "elapsed_ms": 8200,
    "tokens": {"input": 1200, "output": 1850},
    "success_count": 10,
    "filtered_count": 1
  }
}

Response 503:
{"detail": "AI 服务暂不可用，请稍后重试"}
```

### 7.2 题目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/exercises?course_id=&status=` | 查询题目列表（草稿/已发布/已关闭） |
| GET | `/api/v1/exercises/{id}` | 题目详情 |
| PUT | `/api/v1/exercises/{id}` | 教师编辑单题 |
| DELETE | `/api/v1/exercises/{id}` | 删除（软删除） |
| POST | `/api/v1/exercises/publish` | 批量发布：`{exercise_ids:[]}` |
| POST | `/api/v1/exercises/close` | 批量关闭 |
| GET | `/api/v1/ai/exercises/batches` | 查询历史生成批次 |
| GET | `/api/v1/ai/exercises/batches/{batch_id}` | 按批次查题目 |

### 7.3 答题任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/exercise-tasks` | 创建答题任务（选题 + 选班级） |
| GET | `/api/v1/exercise-tasks?course_id=` | 教师查任务列表 |
| GET | `/api/v1/exercise-tasks/my` | 学生查我的待答题任务 |
| GET | `/api/v1/exercise-tasks/{id}` | 任务详情（含题目） |
| POST | `/api/v1/exercise-tasks/{id}/close` | 关闭任务 |

### 7.4 学生答题

```
POST /api/v1/exercises/{id}/answer
Authorization: Bearer <student_token>

Request:
{"task_id": 45, "answer": "A"}    # 或 "ABD" / true / "链表"

Response 200:
{
  "correct": true,
  "score": 5,
  "explanation": "二叉搜索树的中序遍历满足左<根<右...",
  "knowledge_mastery_updated": true,
  "mastery_after": 0.65
}
```

### 7.5 薄弱点推荐（支撑亮点 1）

```
GET /api/v1/courses/{course_id}/weak-knowledge-points?top_k=5

Response 200:
{
  "weak_points": [
    {"kp_id": 7, "name": "红黑树", "correct_rate": 0.32, "affected_students": 12},
    {"kp_id": 9, "name": "平衡二叉树", "correct_rate": 0.45, "affected_students": 8}
  ]
}
```

---

## 8. 前端交互设计

### 8.1 教师出题页（核心）

```
┌──────────────────────────────────────────────────────────────┐
│ AI 出题 · 数据结构与算法                          [课程切换 ▼] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  知识点范围                                                  │
│  ┌────────────────────────────────────────────────┐          │
│  │ ☑ 二叉树遍历  ☑ 红黑树  ☐ 哈希表  ☐ 排序 ...  │          │
│  └────────────────────────────────────────────────┘          │
│  💡 推荐：班级薄弱知识点 Top3（点击勾选）                    │
│     · 红黑树（掌握度 32%）   · 平衡二叉树（45%）             │
│                                                              │
│  题型分布            难度                                   │
│  单选 [ 6 ]  多选 [ 2 ]  判断 [ 2 ]  填空 [ 0 ]   ● 中等    │
│                                                              │
│  额外要求（可选）                                            │
│  ┌────────────────────────────────────────────────┐          │
│  │ 面向初学者，干扰项要合理                       │          │
│  └────────────────────────────────────────────────┘          │
│                                                              │
│              [ 生成题目 ]   预计 10-15 秒                    │
├──────────────────────────────────────────────────────────────┤
│  生成结果 · 批次 #123 · qwen-plus · 8.2s · 3050 tokens       │
│  ┌────────────────────────────────────────────────┐          │
│  │ Q1 [单选][medium] 二叉搜索树的中序遍历...      │ ⚠ 疑似重复│
│  │   A.递增 B.递减 C.无序 D.叶结点   答案:A  [编辑]│          │
│  │ Q2 [多选][hard] 关于红黑树，下列说法正确的...  │ [编辑]   │
│  │ ...                                            │          │
│  └────────────────────────────────────────────────┘          │
│  [全选] [取消选择]    [发布选中题目到班级]                   │
└──────────────────────────────────────────────────────────────┘
```

**关键交互**：
- 生成中显示进度（调用 AI 服务、解析、校验、去重）
- 疑似重复题高亮（黄色 ⚠ 标记）
- 单题编辑弹窗（全字段可改）
- 批量发布前二次确认

### 8.2 学生答题页

```
┌──────────────────────────────────────────────────────────────┐
│ 答题 · 红黑树专题练习                            剩余 12:34  │
├──────────────────────────────────────────────────────────────┤
│  3 / 10                                                      │
│                                                              │
│  Q3 [多选] 关于红黑树，下列说法正确的是（ ）                 │
│                                                              │
│  ☐ A. 每个节点要么红要么黑                                   │
│  ☐ B. 根节点是红色                                           │
│  ☐ C. 红节点的子节点必须是黑                                 │
│  ☐ D. 从任一节点到其叶子路径的黑节点数相同                   │
│                                                              │
│              [上一题]    [下一题]    [提交]                  │
└──────────────────────────────────────────────────────────────┘
```

提交后立即显示判分结果 + 解析：

```
✅ 正确！得分 8/8

解析：红黑树的性质包括：每个节点非黑即红（A对）、根节点是黑色（B错）、
红节点的子节点必须是黑（C对）、从任一节点到叶子的所有路径黑节点数相同（D对）。
所以正确答案是 ACD。
```

---

## 9. 目录结构

```
algorithm/
├── requirements.txt
└── src/
    ├── __init__.py
    ├── main.py                  # FastAPI 入口
    ├── llm_client.py            # 通义千问封装（多厂商可切）
    ├── generator.py             # 出题主逻辑
    ├── schemas.py               # Pydantic 输入输出模型
    └── prompts/
        ├── exercise.py          # 出题 prompt 模板
        └── fewshot/
            ├── data_structure.json   # 408 真题 few-shot
            └── computer_network.json

backend/app/
├── api/v1/
│   ├── ai.py                    # AI 出题调用入口
│   ├── exercises.py             # 题目管理 + 学生答题
│   └── exercise_tasks.py        # 答题任务
├── models/
│   ├── exercise.py              # Exercise / AnswerRecord / ExerciseTask
│   ├── knowledge_point.py       # KnowledgePoint
│   └── ai_call_log.py           # AiCallLog
└── services/
    ├── judge.py                 # 判分纯函数
    ├── dedup.py                 # TF-IDF 去重
    ├── mastery.py               # 掌握度回流
    └── weak_point.py            # 薄弱点推荐
```

---

## 10. 开发任务分解

| 任务 | 位置 | 估时 | 依赖 |
|------|------|------|------|
| 数据模型（Exercise/KP/AnswerRecord/Task/Log） | `backend/app/models/` | 0.5 天 | — |
| LLM 客户端封装（通义千问） | `algorithm/src/llm_client.py` | 0.5 天 | D13 |
| 出题 prompt + Few-shot 素材整理 | `algorithm/src/prompts/` | 0.5 天 | 真题文档 |
| 出题生成服务（含三道防线） | `algorithm/src/generator.py` | 1 天 | LLM 客户端 |
| AI 服务 HTTP 入口 | `algorithm/src/main.py` | 0.3 天 | 生成器 |
| 后端 AI 薄封装接口 | `backend/app/api/v1/ai.py` | 0.5 天 | AI 服务 |
| 题目管理 CRUD | `backend/app/api/v1/exercises.py` | 1 天 | 模型 |
| TF-IDF 去重服务 | `backend/app/services/dedup.py` | 0.3 天 | D12 |
| 判分纯函数 | `backend/app/services/judge.py` | 0.3 天 | 模型 |
| 答题任务接口 | `backend/app/api/v1/exercise_tasks.py` | 0.5 天 | 模型 |
| 学生答题 + 掌握度回流 | `backend/app/services/mastery.py` | 0.5 天 | 判分 |
| 薄弱点推荐接口 | `backend/app/services/weak_point.py` | 0.3 天 | 知识点统计 |
| 教师出题页前端 | `frontend/src/views/teacher/AiExercise.vue` | 1.5 天 | 接口 |
| 学生答题页前端 | `frontend/src/views/student/Exercise.vue` | 1 天 | 接口 |
| 测试（单测 + 联调） | 各模块 | 1 天 | — |
| **合计** | | **≈ 9 天/人** | |

---

## 11. 验收标准

| 项 | 标准 |
|----|------|
| 出题格式 | JSON 格式正确率 100%（抽测 3 门课 × 10 题） |
| 知识点匹配 | 生成的题目 ≥ 90% 属于指定知识点范围 |
| 错题率 | 无明显错题（答案错位、选项重复、题干不完整） |
| 稳定性 | 连续生成 20 次，成功率 ≥ 95% |
| 性能 | 单次 10 题生成 ≤ 15 秒 |
| 判分 | 4 种题型全覆盖，正确率 100%（用例驱动） |
| 去重 | TF-IDF 相似度 ≥ 0.8 的题自动剔除 |
| 掌握度回流 | 答题后知识点掌握度有更新 |
| 可追溯 | AiCallLog 完整记录，可按批次/时间查询 |
| 降级 | LLM 不可用时，系统其他功能不受影响 |

---

## 12. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 服务波动 | 多厂商配置（通义主、智谱/DeepSeek 备），重试机制 |
| 生成题目质量参差 | 三道质量防线 + 教师审核环节不可省 |
| 成本超支 | qwen-plus 有免费额度；预算告警；缓存常见知识点题 |
| 学术诚信 | 入库前去重；每学期补充新题；填空题用等价答案集合 |
| 数据隐私 | prompt 不带学生姓名/学号，只带知识点和统计性数据 |
| Prompt 注入 | extra_requirements 做长度限制（≤200 字）+ 字符过滤 |
| 知识点漂移 | 保留但标注"待人工确认"，不直接发布 |

---

## 13. 与其他模块的关系

| 关联模块 | 关系 |
|---------|------|
| 3.2.10 知识点掌握度 | 出题答题结果 → 异步回流更新掌握度 |
| 3.2.11 异常学情预警 | 答题数据可作为预警规则 W5（薄弱点堆积）的输入 |
| 3.2.8 学情画像 | 答题正确率纳入"学业水平"维度 |
| Agent B（自适应组卷） | 调用本模块的 generate_exercises 工具，配合薄弱点自动组卷 |

---

## 14. 变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 1.0 | 2026-07-08 | 初版 | 思路全开队 |
