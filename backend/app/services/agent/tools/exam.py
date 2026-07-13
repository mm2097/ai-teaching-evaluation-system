"""Agent B 自适应组卷工具集（LLM Tool Loop RAG 出题 Agent）。

工具（对应 LLM_Tool_Loop_RAG出题Agent设计.md §3.2）：
    get_weak_knowledge_points  掌握度查询（复用 queries，agent=both 已注册）
    search_question_bank       题库检索（结构化查询：知识点/题型/难度）
    rag_search_questions       RAG 检索（TF-IDF 语义召回）
    get_recent_used_questions  历史出题查询（近期任务用过的题）
    generate_exercises         AI 生成（题库不足时补题）
    check_duplicate            去重（候选题 vs 已有题）
    compose_paper_plan         组卷（题量/题型/难度/覆盖）
    validate_paper             校验（答案/选项/覆盖率/重复度）
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from sqlmodel import select

from app.models import AiQuestion, KnowledgePoint
from app.services.agent.registry import Tool, ToolContext, ToolRegistry


def _t_get_existing_exercises(ctx: ToolContext, course_id: int = 0, **_) -> dict:
    """查课内已有题目（返回题干+知识点，供去重参考）。"""
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}

    rows = ctx.session.exec(
        select(AiQuestion, KnowledgePoint)
        .join(KnowledgePoint, AiQuestion.point_id == KnowledgePoint.point_id)
        .where(AiQuestion.course_id == cid)
    ).all()
    exercises = []
    for q, kp in rows:
        exercises.append({
            "question_id": q.question_id,
            "content": (q.content[:80] + "...") if len(q.content) > 80 else q.content,
            "knowledge_point": kp.point_name,
            "type": {1: "单选", 2: "多选", 3: "判断", 4: "填空"}.get(q.type, "未知"),
        })
    return {"existing_count": len(exercises), "exercises": exercises[:50]}


def _t_generate_exercises_wrapper(
    ctx: ToolContext,
    course_id: int = 0,
    knowledge_points: list[str] | None = None,
    total_count: int = 5,
    difficulty: str = "medium",
    **_,
) -> dict:
    """调用 algorithm 服务生成题目。

    knowledge_points: 知识点名称列表
    difficulty: easy / medium / hard
    """
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}
    if not knowledge_points:
        return {"error": "需要 knowledge_points"}

    from app.models import Course
    course = ctx.session.get(Course, cid)
    course_name = course.course_name if course else "未知课程"

    try:
        resp = httpx.post(
            "http://127.0.0.1:8001/generate_exercises",
            json={
                "course_name": course_name,
                "course_id": cid,
                "knowledge_points": knowledge_points,
                "total_count": total_count,
                "difficulty": difficulty,
                "question_types": [],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # 只回传题干与知识点（完整内容太长）
        questions = []
        for q in data.get("questions", []):
            questions.append({
                "stem": q.get("stem", "")[:100],
                "type": q.get("type", ""),
                "knowledge_point": q.get("knowledge_point", ""),
                "difficulty": q.get("difficulty", ""),
                "answer": q.get("answer", ""),
            })
        return {
            "generated_count": len(questions),
            "questions": questions,
            "meta": data.get("meta", {}),
        }
    except httpx.HTTPStatusError as e:
        return {"error": f"生成失败 HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except httpx.RequestError as e:
        return {"error": f"算法服务不可达: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"生成异常: {type(e).__name__}: {e}"}


def _t_check_duplicate_wrapper(
    ctx: ToolContext,
    course_id: int = 0,
    new_questions: list[dict] | None = None,
    **_,
) -> dict:
    """检查新题是否与课内已有题重复。"""
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}
    if not new_questions:
        return {"error": "需要 new_questions"}

    from app.services.dedup import check_duplicate_against_bank

    bank_rows = ctx.session.exec(
        select(AiQuestion).where(AiQuestion.course_id == cid)
    ).all()
    bank = [
        {
            "content": q.content,
            "options": json.loads(q.options) if q.options else [],
            "correct_answer": q.correct_answer,
        }
        for q in bank_rows
    ]

    results = []
    for nq in new_questions:
        is_dup, sim, idx = check_duplicate_against_bank(nq, bank)
        results.append({
            "stem": nq.get("content", nq.get("stem", ""))[:60],
            "is_duplicate": is_dup,
            "similarity": sim,
        })
    dup_count = sum(1 for r in results if r["is_duplicate"])
    return {"total_checked": len(results), "duplicate_count": dup_count, "details": results}


def _t_compose_paper_plan(
    ctx: ToolContext,
    course_id: int = 0,
    questions: list[dict] | None = None,
    plan_note: str = "",
    **_,
) -> dict:
    """把已生成的合格题目组装成组卷方案（不入库，返回草稿给教师审核）。"""
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}
    if not questions:
        return {"error": "需要 questions"}

    by_kp: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for q in questions:
        kp = q.get("knowledge_point", "未知")
        by_kp[kp] = by_kp.get(kp, 0) + 1
        tp = q.get("type", "未知")
        by_type[tp] = by_type.get(tp, 0) + 1

    return {
        "status": "draft",
        "course_id": cid,
        "total": len(questions),
        "distribution_by_knowledge_point": by_kp,
        "distribution_by_type": by_type,
        "plan_note": plan_note,
        "questions": questions,
        "next_action": "请教师审核后点击「发布到班级」",
    }


# ===== 新增工具（LLM Tool Loop RAG 出题 Agent） =====

# 题型编号 → 名称映射
_TYPE_MAP = {1: "single_choice", 2: "multiple_choice", 3: "judge", 4: "fill_blank", 5: "short_answer"}
_TYPE_NAME_CN = {1: "单选", 2: "多选", 3: "判断", 4: "填空", 5: "简答"}


def _question_to_dict(q: AiQuestion, kp_name: str = "") -> dict:
    """把 AiQuestion ORM 行转为工具返回的题目 dict。"""
    return {
        "question_id": q.question_id,
        "content": q.content,
        "options": json.loads(q.options) if q.options else [],
        "correct_answer": q.correct_answer,
        "analysis": q.analysis or "",
        "type": _TYPE_MAP.get(q.type, "unknown"),
        "type_cn": _TYPE_NAME_CN.get(q.type, "未知"),
        "knowledge_point": kp_name,
        "difficulty": q.difficulty,
    }


def _t_search_question_bank(
    ctx: ToolContext,
    course_id: int = 0,
    knowledge_points: list[str] | None = None,
    question_types: list[int] | None = None,
    difficulty: str = "",
    limit: int = 20,
    **_,
) -> dict:
    """结构化检索题库：按知识点名称、题型编号、难度过滤。

    question_types: 题型编号列表，1=单选 2=多选 3=判断 4=填空 5=简答
    difficulty: ""=全部 / easy / medium / hard
    """
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}

    stmt = (
        select(AiQuestion, KnowledgePoint)
        .join(KnowledgePoint, AiQuestion.point_id == KnowledgePoint.point_id)
        .where(AiQuestion.course_id == cid)
    )
    if knowledge_points:
        stmt = stmt.where(KnowledgePoint.point_name.in_(knowledge_points))  # type: ignore
    if question_types:
        stmt = stmt.where(AiQuestion.type.in_(question_types))  # type: ignore
    if difficulty:
        stmt = stmt.where(AiQuestion.difficulty == difficulty)

    rows = ctx.session.exec(stmt).all()
    questions = [_question_to_dict(q, kp.point_name) for q, kp in rows]
    return {
        "total": len(questions),
        "questions": questions[:limit],
        "filters": {
            "knowledge_points": knowledge_points or [],
            "question_types": question_types or [],
            "difficulty": difficulty or "all",
        },
    }


def _t_rag_search_questions(
    ctx: ToolContext,
    course_id: int = 0,
    query: str = "",
    top_k: int = 5,
    question_types: list[int] | None = None,
    difficulty: str = "",
    **_,
) -> dict:
    """RAG 语义召回：基于向量嵌入（ChromaDB）检索最相关题目，回退 TF-IDF。

    用途：用户有特殊要求（如"和二叉树遍历相关的题"、"考察时间复杂度的题"）时，
    用语义匹配而非精确知识点过滤。
    """
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}
    if not query or not query.strip():
        return {"error": "需要 query 参数（自然语言描述）"}

    # 优先使用 RagService（向量检索，回退 TF-IDF SQL）
    try:
        from app.services.rag_service import get_rag_service
        rag = get_rag_service()
        results = rag.search(
            ctx.session,
            course_id=cid,
            query=query,
            top_k=top_k,
            knowledge_points=None,
            difficulty=difficulty,
        )

        # 转换格式 + 按题型过滤
        from app.models import KnowledgePoint
        type_names = set()
        if question_types:
            for t in question_types:
                type_names.add(_TYPE_MAP.get(t, ""))

        questions = []
        for item in results:
            q_type = item.get("type", "")
            if type_names and q_type not in type_names:
                continue
            questions.append({
                "question_id": item.get("question_id", 0),
                "content": item.get("content", item.get("stem", "")),
                "options": item.get("options", []),
                "correct_answer": item.get("answer", ""),
                "analysis": item.get("explanation", ""),
                "type": q_type,
                "type_cn": {1: "单选", 2: "多选", 3: "判断", 4: "填空", 5: "简答"}.get(
                    {"single_choice": 1, "multiple_choice": 2, "judge": 3, "fill_blank": 4, "short_answer": 5}.get(q_type, 0), "未知"
                ),
                "knowledge_point": item.get("knowledge_point", ""),
                "difficulty": item.get("difficulty", "medium"),
                "similarity": item.get("similarity", 0),
            })

        return {
            "total": len(questions),
            "query": query,
            "questions": questions[:top_k],
        }
    except Exception as e:  # noqa: BLE001
        # 兜底：回退到原始 TF-IDF 逻辑
        pass

    # ===== TF-IDF 回退路径（RagService 不可用时） =====
    from app.services.dedup import _tokenize, _build_tfidf, _cosine

    # 取候选题
    stmt = (
        select(AiQuestion, KnowledgePoint)
        .join(KnowledgePoint, AiQuestion.point_id == KnowledgePoint.point_id)
        .where(AiQuestion.course_id == cid)
    )
    if question_types:
        stmt = stmt.where(AiQuestion.type.in_(question_types))  # type: ignore
    if difficulty:
        stmt = stmt.where(AiQuestion.difficulty == difficulty)

    rows = ctx.session.exec(stmt).all()
    if not rows:
        return {"total": 0, "questions": [], "query": query}

    # 构建文档：query + 每道题的 content + options + answer
    q_dicts = [_question_to_dict(q, kp.point_name) for q, kp in rows]
    docs = [_tokenize(query)]
    for qd in q_dicts:
        text = qd["content"]
        if qd.get("options"):
            text += " " + " ".join(str(o) for o in qd["options"])
        docs.append(_tokenize(text))

    vecs = _build_tfidf(docs)
    query_vec = vecs[0]

    # 计算相似度并排序
    scored = []
    for i, qd in enumerate(q_dicts):
        sim = _cosine(query_vec, vecs[i + 1])
        scored.append((sim, qd))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for sim, qd in scored[:top_k]:
        qd_out = dict(qd)
        qd_out["similarity"] = round(sim, 3)
        results.append(qd_out)

    return {
        "total": len(results),
        "query": query,
        "questions": results,
    }


def _t_get_recent_used_questions(
    ctx: ToolContext,
    course_id: int = 0,
    recent_count: int = 3,
    **_,
) -> dict:
    """查询近期答题任务中用过的题目（用于避免重复出题）。

    recent_count: 取最近 N 个已发布/已结束的任务
    """
    cid = course_id or ctx.course_id
    if not cid:
        return {"error": "未提供 course_id"}

    from app.models import AnswerTask, TaskQuestion

    # 取近 N 个任务
    tasks = ctx.session.exec(
        select(AnswerTask)
        .where(AnswerTask.course_id == cid, AnswerTask.status >= 1)
        .order_by(AnswerTask.publish_time.desc())
        .limit(recent_count)
    ).all()

    if not tasks:
        return {"tasks": [], "used_questions": [], "used_question_ids": []}

    task_list = list(tasks)
    if not task_list:
        return {"tasks": [], "used_questions": [], "used_question_ids": []}

    task_ids = [t.task_id for t in task_list]
    task_info = [
        {"task_id": t.task_id, "task_name": t.task_name, "status": t.status}
        for t in task_list
    ]

    # 取这些任务关联的题目
    tq_rows = ctx.session.exec(
        select(TaskQuestion, AiQuestion, KnowledgePoint)
        .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
        .join(KnowledgePoint, AiQuestion.point_id == KnowledgePoint.point_id)
        .where(TaskQuestion.task_id.in_(task_ids))  # type: ignore
    ).all()

    used_map: dict[int, dict] = {}
    for tq, q, kp in tq_rows:
        if q.question_id not in used_map:
            used_map[q.question_id] = {
                "question_id": q.question_id,
                "content": q.content[:100],
                "knowledge_point": kp.point_name,
                "type": _TYPE_NAME_CN.get(q.type, "未知"),
                "used_in_tasks": [],
            }
        used_map[q.question_id]["used_in_tasks"].append(tq.task_id)

    return {
        "tasks": task_info,
        "used_questions": list(used_map.values()),
        "used_question_ids": list(used_map.keys()),
    }


def _t_validate_paper(
    ctx: ToolContext,
    course_id: int = 0,
    questions: list[dict] | None = None,
    target_count: int = 0,
    target_types: dict | None = None,
    target_knowledge_points: list[str] | None = None,
    **_,
) -> dict:
    """校验组卷方案：检查答案完整性、选项合法性、知识点覆盖、题型比例、内部重复度。

    target_types: {"single_choice": 5, "judge": 3, ...} 目标题型分布
    target_knowledge_points: 目标覆盖的知识点名称列表
    """
    if not questions:
        return {"error": "需要 questions"}

    cid = course_id or ctx.course_id
    issues: list[str] = []
    warnings: list[str] = []

    # 1. 逐题校验答案与选项
    valid_types = set(_TYPE_MAP.values())
    for i, q in enumerate(questions):
        qid = q.get("question_id", f"第{i+1}题")
        q_type = q.get("type", "")
        answer = q.get("correct_answer", q.get("answer", ""))
        options = q.get("options", [])

        if not answer:
            issues.append(f"{qid}：缺少答案")
        if q_type in ("single_choice", "multiple_choice"):
            if not options or len(options) < 2:
                issues.append(f"{qid}：选择题选项不足")
            elif q_type == "single_choice" and answer and answer not in ["A", "B", "C", "D"][:len(options)]:
                warnings.append(f"{qid}：单选答案 '{answer}' 可能不在选项范围内")
        elif q_type == "judge" and answer and answer not in ("true", "false", "对", "错", "T", "F"):
            warnings.append(f"{qid}：判断题答案 '{answer}' 格式不规范")

    # 2. 内部重复检测（TF-IDF）
    from app.services.dedup import dedup_questions
    dedup_input = [
        {"content": q.get("content", q.get("stem", "")),
         "options": q.get("options", []),
         "correct_answer": q.get("correct_answer", q.get("answer", ""))}
        for q in questions
    ]
    dedup_result = dedup_questions(dedup_input, threshold=0.8)
    if dedup_result.duplicates:
        for d in dedup_result.duplicates:
            issues.append(f"第{d['index']+1}题与第{d['dup_of']+1}题重复（相似度 {d['similarity']}）")

    # 3. 题量校验
    if target_count and len(questions) < target_count:
        warnings.append(f"题量不足：目标 {target_count} 题，当前 {len(questions)} 题")

    # 4. 题型分布校验
    actual_types: dict[str, int] = {}
    for q in questions:
        tp = q.get("type", "unknown")
        actual_types[tp] = actual_types.get(tp, 0) + 1
    if target_types:
        for tp, target_n in target_types.items():
            actual_n = actual_types.get(tp, 0)
            if actual_n < target_n:
                warnings.append(f"题型 {tp} 不足：目标 {target_n} 题，当前 {actual_n} 题")

    # 5. 知识点覆盖校验
    actual_kps: set[str] = set()
    for q in questions:
        kp = q.get("knowledge_point", "")
        if kp:
            actual_kps.add(kp)
    if target_knowledge_points:
        missing = set(target_knowledge_points) - actual_kps
        if missing:
            warnings.append(f"未覆盖的知识点：{', '.join(missing)}")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "total_questions": len(questions),
            "actual_types": actual_types,
            "actual_knowledge_points": list(actual_kps),
            "internal_duplicates": len(dedup_result.duplicates),
        },
        "next_action": "通过校验，可组装组卷方案" if passed else "请修复 issues 后再组卷",
    }


def register_exam_tools(registry: ToolRegistry) -> None:
    """注册 Agent B 工具（LLM Tool Loop RAG 出题 Agent）。"""
    tools = [
        # 1. 题库检索（结构化查询）
        Tool(
            name="search_question_bank",
            description=(
                "结构化检索题库：按知识点名称、题型编号、难度过滤。"
                "题型编号：1=单选 2=多选 3=判断 4=填空 5=简答。"
                "适合教师给出明确知识点和题型要求时使用。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "knowledge_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "知识点名称列表",
                    },
                    "question_types": {
                        "type": "array",
                        "items": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                        "description": "题型编号列表（1单选2多选3判断4填空5简答）",
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["", "easy", "medium", "hard"],
                        "description": "难度过滤，空串=全部",
                    },
                    "limit": {"type": "integer", "default": 20, "description": "最多返回条数"},
                },
            },
            handler=_t_search_question_bank,
            category="query",
            agent="both",
        ),
        # 2. RAG 检索（语义召回）
        Tool(
            name="rag_search_questions",
            description=(
                "RAG 语义召回：基于 TF-IDF 余弦相似度，按自然语言描述检索最相关的题目。"
                "适合教师有特殊要求时使用，如'和二叉树遍历相关的题'、'考察时间复杂度的题'。"
                "返回按相似度排序的 Top K 题目。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "query": {
                        "type": "string",
                        "description": "自然语言查询，如'二叉树遍历'、'排序算法的时间复杂度'",
                    },
                    "top_k": {"type": "integer", "default": 5, "description": "返回前 K 条"},
                    "question_types": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "可选：限制题型",
                    },
                    "difficulty": {"type": "string", "description": "可选：限制难度"},
                },
                "required": ["query"],
            },
            handler=_t_rag_search_questions,
            category="query",
            agent="both",
        ),
        # 3. 历史出题查询
        Tool(
            name="get_recent_used_questions",
            description=(
                "查询近期答题任务中已用过的题目（用于避免重复出题）。"
                "返回最近 N 个任务及其用过的题目列表和题目 ID。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "recent_count": {
                        "type": "integer",
                        "default": 3,
                        "description": "取最近 N 个已发布的任务",
                    },
                },
            },
            handler=_t_get_recent_used_questions,
            category="query",
            agent="both",
        ),
        # 4. 历史已有题目概览（保留原 get_existing_exercises 语义）
        Tool(
            name="get_existing_exercises",
            description="查询课内已有 AI 题目（题干+知识点），用于快速了解题库规模。",
            parameters={
                "type": "object",
                "properties": {"course_id": {"type": "integer"}},
            },
            handler=_t_get_existing_exercises,
            category="query",
            agent="both",
        ),
        # 5. AI 生成（题库不足时补题）
        Tool(
            name="generate_exercises",
            description=(
                "调用 AI 生成新题目。当题库检索 + RAG 召回的候选题不足时使用。"
                "需提供知识点名称列表与数量。难度可选 easy/medium/hard。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "knowledge_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "知识点名称列表",
                    },
                    "total_count": {"type": "integer", "default": 5},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"], "default": "medium"},
                },
                "required": ["knowledge_points"],
            },
            handler=_t_generate_exercises_wrapper,
            category="query",
            agent="both",
        ),
        # 6. 去重
        Tool(
            name="check_duplicate",
            description="检查新题是否与课内已有题重复（TF-IDF 余弦相似度，阈值 0.8）。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "new_questions": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "待检查的题目列表，每项含 content/stem 字段",
                    },
                },
                "required": ["new_questions"],
            },
            handler=_t_check_duplicate_wrapper,
            category="query",
            agent="both",
        ),
        # 7. 组卷
        Tool(
            name="compose_paper_plan",
            description=(
                "把已校验合格的题目组装成组卷方案（草稿态，不入库，等待教师审核发布）。"
                "调用前请先用 validate_paper 确认题目合格。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "questions": {"type": "array", "items": {"type": "object"}},
                    "plan_note": {"type": "string", "description": "组卷说明"},
                },
                "required": ["questions"],
            },
            handler=_t_compose_paper_plan,
            category="query",
            agent="both",
        ),
        # 8. 校验
        Tool(
            name="validate_paper",
            description=(
                "校验组卷方案：检查答案完整性、选项合法性、知识点覆盖、题型比例、内部重复度。"
                "在 compose_paper_plan 之前调用，确保方案质量。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "questions": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "待校验的题目列表",
                    },
                    "target_count": {"type": "integer", "description": "目标题量"},
                    "target_types": {
                        "type": "object",
                        "description": "目标题型分布，如 {\"single_choice\": 5, \"judge\": 3}",
                    },
                    "target_knowledge_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "目标覆盖知识点名称列表",
                    },
                },
                "required": ["questions"],
            },
            handler=_t_validate_paper,
            category="query",
            agent="both",
        ),
    ]
    for t in tools:
        registry.register(t)
