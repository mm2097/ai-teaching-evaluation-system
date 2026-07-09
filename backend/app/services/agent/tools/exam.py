"""Agent B 自适应组卷工具集。

工具：
    get_weak_knowledge_points  （复用 queries，agent=both 已注册）
    get_existing_exercises      查课内已有题（避免重复）
    generate_exercises_wrapper  调 algorithm 8001 生成题
    check_duplicate_wrapper     新题与已有题去重
    compose_paper_plan          组卷方案（不直接入库，返回草稿）
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


def register_exam_tools(registry: ToolRegistry) -> None:
    """注册 Agent B 工具。"""
    tools = [
        Tool(
            name="get_existing_exercises",
            description="查询课内已有 AI 题目（题干+知识点），用于避免重复出题。",
            parameters={
                "type": "object",
                "properties": {"course_id": {"type": "integer"}},
            },
            handler=_t_get_existing_exercises,
            category="query",
            agent="both",
        ),
        Tool(
            name="generate_exercises",
            description="调用 AI 生成题目。需提供知识点名称列表与数量。难度可选 easy/medium/hard。",
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
        Tool(
            name="compose_paper_plan",
            description="把已生成的合格题目组装成组卷方案（草稿态，不入库，等待教师审核发布）。",
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
            category="query",  # 不落库，归类为 query（真正入库需教师确认）
            agent="both",
        ),
    ]
    for t in tools:
        registry.register(t)
