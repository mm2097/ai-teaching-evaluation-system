"""题库管理 API。

接口：
    GET    /api/v1/question-bank            题库列表（按课程过滤）
    POST   /api/v1/question-bank            批量新增题目
    POST   /api/v1/question-bank/check      检查题干是否已存在
    GET    /api/v1/question-bank/templates  内置模板列表
    GET    /api/v1/question-bank/stats      题库统计
    PUT    /api/v1/question-bank/{id}       更新单题
    DELETE /api/v1/question-bank/{id}       删除单题
    POST   /api/v1/question-bank/import-builtin  从内置模板导入
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, or_, select

from app.core.database import get_session
from app.models import (
    AiQuestion,
    Course,
    KnowledgePoint,
    KnowledgeModule,
)

router = APIRouter()

# type 映射（与 models/question.py、quiz.py 一致：5=简答）
_TYPE_STR_TO_INT = {
    "single_choice": 1,
    "multi_choice": 2,
    "judge": 3,
    "fill_blank": 4,
    "short_answer": 5,
}
_TYPE_INT_TO_STR = {v: k for k, v in _TYPE_STR_TO_INT.items()}


def _difficulty_str(score: int) -> str:
    if score < 3:
        return "easy"
    if score <= 7:
        return "medium"
    return "hard"


# ===== 请求/响应模型 =====

class AddQuestionItem(BaseModel):
    """批量新增的单条题目。"""
    courseId: int
    type: str = "single_choice"
    stem: str
    options: list[dict[str, str]] | None = None
    answer: str
    answerList: list[str] | None = None
    explanation: str | None = None
    knowledgePoint: str | None = None
    difficulty: str = "medium"
    score: float = 0


class AddQuestionsRequest(BaseModel):
    questions: list[AddQuestionItem]
    source: str = "manual"


class CheckDuplicateRequest(BaseModel):
    stems: list[str]
    courseId: int


class ImportRowsRequest(BaseModel):
    """从解析后的文件行导入。"""
    courseId: int
    rows: list[dict[str, Any]]


class ImportBuiltinRequest(BaseModel):
    courseId: int
    templateId: str


class UpdateQuestionRequest(BaseModel):
    """更新单题请求体。"""
    type: str = "single_choice"
    stem: str = ""
    options: list[dict[str, str]] | None = None
    answer: str = ""
    answerList: list[str] | None = None
    explanation: str | None = None
    knowledgePoint: str | None = None
    difficulty: str = "medium"
    score: float = 0


# ===== 知识点辅助 =====

def _find_or_create_knowledge_point(session: Session, course_id: int, name: str) -> int:
    """按名字找知识点，找不到则在课程第一个模块下创建。"""
    stmt = (
        select(KnowledgePoint)
        .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
        .where(KnowledgeModule.course_id == course_id, KnowledgePoint.point_name == name)
    )
    kp = session.exec(stmt).first()
    if kp:
        return kp.point_id

    # 找该课程第一个模块
    module = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id).limit(1)
    ).first()
    if not module:
        module = KnowledgeModule(course_id=course_id, module_name="默认模块")
        session.add(module)
        session.commit()
        session.refresh(module)

    kp = KnowledgePoint(module_id=module.module_id, point_name=name)
    session.add(kp)
    session.commit()
    session.refresh(kp)
    return kp.point_id


# ===== 接口 =====

@router.get("/question-bank", tags=["题库管理"])
def list_question_bank(
    course_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """题库列表。"""
    stmt = select(AiQuestion)
    if course_id:
        stmt = stmt.where(AiQuestion.course_id == course_id)
    questions = session.exec(stmt.order_by(AiQuestion.question_id.desc())).all()

    result = []
    for q in questions:
        course = session.get(Course, q.course_id)
        kp = session.get(KnowledgePoint, q.point_id)
        options = []
        if q.options:
            try:
                options = json.loads(q.options)
            except (json.JSONDecodeError, TypeError):
                options = []

        result.append({
            "id": q.question_id,
            "courseId": q.course_id,
            "courseName": course.course_name if course else "",
            "knowledgePoint": kp.point_name if kp else "",
            "type": _TYPE_INT_TO_STR.get(q.type, "single_choice"),
            "content": q.content,
            "options": options,
            "answer": q.correct_answer,
            "explanation": q.analysis or "",
            "difficulty": _difficulty_str(len(q.content) % 10),
            "status": status or "published",
            "createdTime": q.create_time.strftime("%Y-%m-%d %H:%M") if q.create_time else "",
        })

    return result


@router.post("/question-bank", tags=["题库管理"])
def add_questions_to_bank(
    req: AddQuestionsRequest,
    session: Session = Depends(get_session),
) -> dict:
    """批量新增题目到题库。"""
    added = 0
    skipped = 0

    for item in req.questions:
        # 检查题干是否已存在
        exists = session.exec(
            select(func.count(AiQuestion.question_id)).where(
                AiQuestion.course_id == item.courseId,
                AiQuestion.content == item.stem,
            )
        ).one()
        if exists:
            skipped += 1
            continue

        # 找知识点
        point_id = 0
        if item.knowledgePoint:
            point_id = _find_or_create_knowledge_point(session, item.courseId, item.knowledgePoint)
        if not point_id:
            # 兜底：课程第一个知识点
            kp = session.exec(
                select(KnowledgePoint)
                .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
                .where(KnowledgeModule.course_id == item.courseId)
                .limit(1)
            ).first()
            point_id = kp.point_id if kp else 0

        if not point_id:
            skipped += 1
            continue

        options_str = None
        if item.options:
            options_str = json.dumps(item.options, ensure_ascii=False)

        answer = item.answer
        if item.answerList:
            answer = ",".join(item.answerList)

        q = AiQuestion(
            course_id=item.courseId,
            point_id=point_id,
            type=_TYPE_STR_TO_INT.get(item.type, 1),
            content=item.stem,
            options=options_str,
            correct_answer=answer,
            analysis=item.explanation,
            create_by=1,
        )
        session.add(q)
        added += 1

    session.commit()
    return {"added": added, "skipped": skipped}


@router.post("/question-bank/check", tags=["题库管理"])
def check_questions_in_bank(
    req: CheckDuplicateRequest,
    session: Session = Depends(get_session),
) -> dict:
    """检查题干列表哪些已存在于题库。返回 { stem: bool }。"""
    if not req.stems:
        return {"status": {}}

    rows = session.exec(
        select(AiQuestion.content).where(
            AiQuestion.course_id == req.courseId,
            AiQuestion.content.in_(req.stems),
        )
    ).all()
    existing = set(rows)

    return {"status": {s: s in existing for s in req.stems}}


@router.get("/question-bank/stats", tags=["题库管理"])
def question_bank_stats(
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """题库统计（按课程维度聚合题型/难度/来源分布）。"""
    stmt = select(AiQuestion)
    if course_id:
        stmt = stmt.where(AiQuestion.course_id == course_id)
    questions = session.exec(stmt).all()

    by_type = {"single_choice": 0, "multi_choice": 0, "judge": 0, "fill_blank": 0, "short_answer": 0}
    by_source = {"ai": 0, "manual": 0, "import": 0}
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}

    for q in questions:
        type_str = _TYPE_INT_TO_STR.get(q.type, "single_choice")
        if type_str in by_type:
            by_type[type_str] += 1
        diff_str = _difficulty_str(len(q.content) % 10)
        if diff_str in by_difficulty:
            by_difficulty[diff_str] += 1
        by_source["manual"] += 1  # 当前所有题均归为 manual

    return {
        "total": len(questions),
        "byType": by_type,
        "bySource": by_source,
        "byDifficulty": by_difficulty,
    }


@router.put("/question-bank/{question_id}", tags=["题库管理"])
def update_question(
    question_id: int,
    req: UpdateQuestionRequest,
    session: Session = Depends(get_session),
) -> dict:
    """更新单题（题干、答案、选项、知识点等）。"""
    q = session.get(AiQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    if req.stem:
        q.content = req.stem
    if req.options is not None:
        q.options = json.dumps(req.options, ensure_ascii=False) if req.options else None
    if req.answer:
        answer = req.answer
        if req.answerList:
            answer = ",".join(req.answerList)
        q.correct_answer = answer
    if req.explanation is not None:
        q.analysis = req.explanation
    if req.type:
        q.type = _TYPE_STR_TO_INT.get(req.type, q.type)
    if req.knowledgePoint:
        point_id = _find_or_create_knowledge_point(session, q.course_id, req.knowledgePoint)
        if point_id:
            q.point_id = point_id

    session.add(q)
    session.commit()
    return {"id": q.question_id, "message": "更新成功"}


@router.delete("/question-bank/{question_id}", tags=["题库管理"])
def delete_question(
    question_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """删除单题（同时清理任务关联）。"""
    q = session.get(AiQuestion, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 清理 task_question 关联
    from app.models import TaskQuestion
    links = session.exec(
        select(TaskQuestion).where(TaskQuestion.question_id == question_id)
    ).all()
    for link in links:
        session.delete(link)

    session.delete(q)
    session.commit()
    return {"id": question_id, "message": "已删除"}


@router.get("/question-bank/templates", tags=["题库管理"])
def list_builtin_templates(
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """内置题库模板（按课程分类）。"""
    templates = [
        {
            "id": "tpl-ds-basic",
            "name": "数据结构基础练习",
            "courseId": 1,
            "courseName": "数据结构",
            "questionCount": 10,
            "description": "二叉树、红黑树、排序算法基础题目",
        },
        {
            "id": "tpl-net-basic",
            "name": "计算机网络基础练习",
            "courseId": 2,
            "courseName": "计算机网络",
            "questionCount": 8,
            "description": "OSI模型、TCP/IP协议族基础题目",
        },
        {
            "id": "tpl-os-basic",
            "name": "操作系统基础练习",
            "courseId": 3,
            "courseName": "操作系统",
            "questionCount": 8,
            "description": "进程管理、内存管理、文件系统",
        },
    ]
    if course_id:
        templates = [t for t in templates if t["courseId"] == course_id]
    return templates


@router.post("/question-bank/import-rows", tags=["题库管理"])
def import_questions_from_file(
    req: ImportRowsRequest,
    session: Session = Depends(get_session),
) -> dict:
    """从解析后的文件行批量导入题目。"""
    added = 0
    skipped = 0

    for row in req.rows:
        stem = row.get("stem", "").strip()
        if not stem:
            skipped += 1
            continue

        # 检查重复
        exists = session.exec(
            select(func.count(AiQuestion.question_id)).where(
                AiQuestion.course_id == req.courseId,
                AiQuestion.content == stem,
            )
        ).one()
        if exists:
            skipped += 1
            continue

        # 知识点
        kp_name = row.get("knowledgePoint", "综合")
        point_id = _find_or_create_knowledge_point(session, req.courseId, kp_name)

        # 选项
        options_str = None
        opts = row.get("options")
        if opts:
            options_str = json.dumps(opts, ensure_ascii=False)

        q_type = _TYPE_STR_TO_INT.get(row.get("type", "single_choice"), 1)
        answer = row.get("answer", "")
        if row.get("answerList"):
            answer = ",".join(row["answerList"])

        q = AiQuestion(
            course_id=req.courseId,
            point_id=point_id,
            type=q_type,
            content=stem,
            options=options_str,
            correct_answer=str(answer),
            analysis=row.get("explanation"),
            create_by=1,
        )
        session.add(q)
        added += 1

    session.commit()
    return {"imported": added, "skipped": skipped}


# 内置模板题目数据
_BUILTIN_QUESTIONS: dict[str, list[dict[str, Any]]] = {
    "tpl-ds-basic": [
        {"type": "single_choice", "stem": "二叉树第i层最多有多少个节点？", "knowledgePoint": "二叉树",
         "options": [{"key":"A","text":"2^(i-1)"},{"key":"B","text":"2^i"},{"key":"C","text":"2i"},{"key":"D","text":"i"}],
         "answer": "A", "explanation": "二叉树第i层最多有2^(i-1)个节点"},
        {"type": "single_choice", "stem": "红黑树中，从任一节点到其每个叶子的所有路径都包含相同数量的什么节点？", "knowledgePoint": "红黑树",
         "options": [{"key":"A","text":"红色节点"},{"key":"B","text":"黑色节点"},{"key":"C","text":"所有节点"},{"key":"D","text":"内部节点"}],
         "answer": "B", "explanation": "红黑树性质：从任一节点到其每个叶子的所有路径都包含相同数目的黑色节点"},
        {"type": "single_choice", "stem": "快速排序的平均时间复杂度是？", "knowledgePoint": "快速排序",
         "options": [{"key":"A","text":"O(n)"},{"key":"B","text":"O(n log n)"},{"key":"C","text":"O(n²)"},{"key":"D","text":"O(log n)"}],
         "answer": "B", "explanation": "快速排序平均时间复杂度为O(n log n)"},
        {"type": "judge", "stem": "二叉搜索树的中序遍历结果是有序的。", "knowledgePoint": "二叉树",
         "answer": "对", "explanation": "BST中序遍历得到有序序列"},
        {"type": "judge", "stem": "堆排序是稳定排序。", "knowledgePoint": "堆排序",
         "answer": "错", "explanation": "堆排序是不稳定排序"},
    ],
    "tpl-net-basic": [
        {"type": "single_choice", "stem": "OSI参考模型共有几层？", "knowledgePoint": "OSI模型",
         "options": [{"key":"A","text":"5"},{"key":"B","text":"6"},{"key":"C","text":"7"},{"key":"D","text":"8"}],
         "answer": "C", "explanation": "OSI参考模型共7层"},
        {"type": "single_choice", "stem": "TCP协议工作在OSI模型的哪一层？", "knowledgePoint": "TCP/IP",
         "options": [{"key":"A","text":"物理层"},{"key":"B","text":"数据链路层"},{"key":"C","text":"网络层"},{"key":"D","text":"传输层"}],
         "answer": "D", "explanation": "TCP是传输层协议"},
        {"type": "judge", "stem": "UDP是面向连接的协议。", "knowledgePoint": "UDP",
         "answer": "错", "explanation": "UDP是无连接协议"},
    ],
    "tpl-os-basic": [
        {"type": "single_choice", "stem": "进程的三种基本状态不包括？", "knowledgePoint": "进程管理",
         "options": [{"key":"A","text":"就绪"},{"key":"B","text":"执行"},{"key":"C","text":"阻塞"},{"key":"D","text":"挂起"}],
         "answer": "D", "explanation": "进程三种基本状态：就绪、执行、阻塞"},
        {"type": "single_choice", "stem": "分页存储管理中，页的大小是？", "knowledgePoint": "内存管理",
         "options": [{"key":"A","text":"可变"},{"key":"B","text":"固定"},{"key":"C","text":"由程序决定"},{"key":"D","text":"由用户决定"}],
         "answer": "B", "explanation": "分页系统中页大小固定"},
    ],
}


@router.post("/question-bank/import-builtin", tags=["题库管理"])
def import_questions_from_builtin(
    req: ImportBuiltinRequest,
    session: Session = Depends(get_session),
) -> dict:
    """从内置模板导入题目。"""
    questions = _BUILTIN_QUESTIONS.get(req.templateId, [])
    if not questions:
        return {"imported": 0, "skipped": 0}

    added = 0
    skipped = 0

    for q_data in questions:
        # 检查重复
        exists = session.exec(
            select(func.count(AiQuestion.question_id)).where(
                AiQuestion.course_id == req.courseId,
                AiQuestion.content == q_data["stem"],
            )
        ).one()
        if exists:
            skipped += 1
            continue

        kp_name = q_data.get("knowledgePoint", "综合")
        point_id = _find_or_create_knowledge_point(session, req.courseId, kp_name)

        options_str = None
        opts = q_data.get("options")
        if opts:
            options_str = json.dumps(opts, ensure_ascii=False)

        q = AiQuestion(
            course_id=req.courseId,
            point_id=point_id,
            type=_TYPE_STR_TO_INT.get(q_data.get("type", "single_choice"), 1),
            content=q_data["stem"],
            options=options_str,
            correct_answer=q_data.get("answer", ""),
            analysis=q_data.get("explanation"),
            create_by=1,
        )
        session.add(q)
        added += 1

    session.commit()
    return {"imported": added, "skipped": skipped}
