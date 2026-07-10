"""答题任务与记录 API。

接口：
    GET  /api/v1/answer-tasks              答题任务列表（教师视角）
    POST /api/v1/answer-tasks              创建/保存答题任务
    POST /api/v1/answer-tasks/{id}/publish 发布任务
    POST /api/v1/answer-tasks/{id}/close   关闭任务
    GET  /api/v1/answer-records            答题记录列表（按任务/学生聚合）
    POST /api/v1/exercises/generate        AI 生成题目（代理算法服务）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.models import (
    AiQuestion,
    AnswerTask,
    ClassInfo,
    Course,
    KnowledgeModule,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
    TaskQuestion,
    Teacher,
)

router = APIRouter()

# status 映射：DB int → 前端 string
_STATUS_MAP = {0: "draft", 1: "published", 2: "closed"}
_TYPE_MAP = {1: "single_choice", 2: "multi_choice", 3: "judge", 4: "fill_blank", 5: "short_answer"}


@router.get("/answer-tasks", tags=["答题管理"])
def list_answer_tasks(
    course_id: int | None = Query(default=None),
    teacher_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """答题任务列表（含题目数、总分、课程/班级名称）。"""
    stmt = select(AnswerTask)
    if course_id:
        stmt = stmt.where(AnswerTask.course_id == course_id)
    if teacher_id:
        # 通过 Course 过滤 teacher
        stmt = stmt.join(Course, AnswerTask.course_id == Course.course_id).where(
            Course.teacher_id == teacher_id
        )
    stmt = stmt.order_by(AnswerTask.publish_time.desc())

    tasks = session.exec(stmt).all()
    result = []
    for t in tasks:
        course = session.get(Course, t.course_id)
        teacher = session.get(Teacher, course.teacher_id) if course else None

        # 题目数与总分
        tq_rows = session.exec(
            select(TaskQuestion, AiQuestion)
            .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
            .where(TaskQuestion.task_id == t.task_id)
            .order_by(TaskQuestion.sort_num)
        ).all()
        questions = []
        total_score = 0.0
        for idx, (tq, q) in enumerate(tq_rows):
            score = 100.0 / max(len(tq_rows), 1)  # 均分
            total_score += score
            kp = session.get(KnowledgePoint, q.point_id)
            questions.append({
                "id": q.question_id,
                "stem": q.content,
                "type": _TYPE_MAP.get(q.type, "single_choice"),
                "knowledgePoint": kp.point_name if kp else "",
                "score": round(score, 1),
                "options": [],
                "answer": q.correct_answer,
                "explanation": q.analysis or "",
                "difficulty": q.difficulty or "medium",
            })

        # 班级名（AnswerTask 没有直接关联班级，用课程下第一个班级兜底）
        class_name = ""
        class_id = 0
        from app.models import CourseStudent
        first_sid = session.exec(
            select(CourseStudent.student_id)
            .where(CourseStudent.course_id == t.course_id)
            .limit(1)
        ).first()
        if first_sid:
            stu = session.get(Student, first_sid)
            if stu:
                class_id = stu.class_id
                cls = session.get(ClassInfo, class_id)
                class_name = cls.class_name if cls else ""

        result.append({
            "id": t.task_id,
            "title": t.task_name,
            "courseId": t.course_id,
            "courseName": course.course_name if course else "",
            "classId": class_id,
            "className": class_name,
            "teacherName": teacher.real_name if teacher else "",
            "knowledgePoints": list({q["knowledgePoint"] for q in questions if q["knowledgePoint"]}),
            "questionCount": len(questions),
            "totalScore": round(total_score) if questions else 100,
            "status": _STATUS_MAP.get(t.status, "draft"),
            "publishTime": t.publish_time.strftime("%Y-%m-%d %H:%M") if t.publish_time else "",
            "deadline": t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else "",
            "questions": questions,
        })

    return result


@router.get("/answer-records", tags=["答题管理"])
def list_answer_records(
    task_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """答题记录列表（按 task+student 聚合，一条 = 一次提交）。"""
    stmt = select(StudentAnswerRecord)
    if task_id:
        stmt = stmt.where(StudentAnswerRecord.task_id == task_id)
    if student_id:
        stmt = stmt.where(StudentAnswerRecord.student_id == student_id)
    if course_id:
        stmt = stmt.join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id).where(
            AiQuestion.course_id == course_id
        )

    all_records = session.exec(stmt).all()

    # 按 (task_id, student_id) 聚合
    grouped: dict[tuple[int, int], list[StudentAnswerRecord]] = {}
    for r in all_records:
        grouped.setdefault((r.task_id, r.student_id), []).append(r)

    result = []
    for (tid, sid), records in grouped.items():
        stu = session.get(Student, sid)
        task = session.get(AnswerTask, tid)

        # 该任务的题目数（用于算总分）
        q_count = session.exec(
            select(func.count(TaskQuestion.rel_id)).where(TaskQuestion.task_id == tid)
        ).one()
        total_score = 100.0
        obtained = sum(float(r.score) for r in records)

        result.append({
            "id": records[0].answer_id,
            "assignmentId": tid,
            "studentId": sid,
            "studentName": stu.real_name if stu else "",
            "studentNo": stu.student_no if stu else "",
            "courseName": "",
            "score": round(obtained, 1),
            "totalScore": round(total_score),
            "submitTime": records[0].submit_time.strftime("%Y-%m-%d %H:%M") if records[0].submit_time else "",
            "status": "submitted",
        })

    # 按提交时间倒序
    result.sort(key=lambda x: x["submitTime"], reverse=True)
    return result


class SubmitAnswersRequest(BaseModel):
    """学生提交答题。"""

    task_id: int
    answers: dict[str, str] = {}  # {question_id: student_answer}
    student_id: int = 1  # 默认 1（MVP 无登录态时的兜底）


@router.post("/answer-records", tags=["答题管理"])
def submit_answers(
    req: SubmitAnswersRequest,
    session: Session = Depends(get_session),
) -> dict:
    """学生提交答题答案。

    客观题（type 1-4）：规则判分
    简答题（type 5）：调算法服务 8001 AI 判分
    """
    # 查任务关联的题目
    tq_rows = session.exec(
        select(TaskQuestion, AiQuestion)
        .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
        .where(TaskQuestion.task_id == req.task_id)
        .order_by(TaskQuestion.sort_num)
    ).all()

    if not tq_rows:
        raise HTTPException(status_code=404, detail="任务不存在或无题目")

    total_score = 0.0
    correct_count = 0
    records_created = 0

    for idx, (tq, question) in enumerate(tq_rows):
        qid = str(question.question_id)
        user_answer = req.answers.get(qid, "")
        per_score = 100.0 / max(len(tq_rows), 1)

        if question.type == 5:
            # 简答题：调 AI 判分
            ai_result = _call_ai_judge(session, question, user_answer, req.student_id, req.task_id)
            if ai_result["score"] is not None:
                total_score += ai_result["score"] * per_score / 10.0  # AI 给 0-10 分，映射到 per_score
                if ai_result["score"] >= 6.0:
                    correct_count += 1
            records_created += 1
        else:
            # 客观题：规则判分
            is_correct = _judge_objective(question, user_answer)
            score = per_score if is_correct else 0
            record = StudentAnswerRecord(
                task_id=req.task_id,
                question_id=question.question_id,
                student_id=req.student_id,
                user_answer=user_answer,
                score=score,
                is_correct=1 if is_correct else 0,
            )
            session.add(record)
            total_score += score
            if is_correct:
                correct_count += 1
            records_created += 1

    session.commit()

    return {
        "submissionId": 0,
        "score": round(total_score, 1),
        "totalScore": 100,
        "correctCount": correct_count,
    }


def _judge_objective(question: AiQuestion, user_answer: str) -> bool:
    """客观题规则判分。"""
    correct = question.correct_answer.strip()
    user = user_answer.strip()

    if question.type == 1:
        # 单选
        return user.upper() == correct.upper()
    elif question.type == 2:
        # 多选：答案排序后比较
        import json as _json
        try:
            correct_list = _json.loads(correct) if correct.startswith("[") else list(correct)
            user_list = _json.loads(user) if user.startswith("[") else list(user)
        except (ValueError, TypeError):
            correct_list = list(correct)
            user_list = list(user)
        return sorted([str(x).upper() for x in correct_list]) == sorted([str(x).upper() for x in user_list])
    elif question.type == 3:
        # 判断
        correct_val = correct in ("正确", "true", "True", "1")
        user_val = user in ("正确", "true", "True", "1")
        return correct_val == user_val
    elif question.type == 4:
        # 填空：忽略大小写比较
        return user.lower() == correct.lower()
    return False


def _call_ai_judge(
    session: Session,
    question: AiQuestion,
    student_answer: str,
    student_id: int,
    task_id: int,
) -> dict:
    """调算法服务 AI 判分并存储记录。"""
    payload = {
        "question_stem": question.content,
        "reference_answer": question.correct_answer,
        "student_answer": student_answer,
        "max_score": 10.0,
    }
    try:
        resp = httpx.post("http://127.0.0.1:8001/judge_answer", json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.RequestError):
        # 算法服务不可达，存待人工判分
        record = StudentAnswerRecord(
            task_id=task_id,
            question_id=question.question_id,
            student_id=student_id,
            user_answer=student_answer,
            score=0,
            is_correct=0,
            ai_score=None,
            judge_reason="AI 服务不可达，需人工判分",
        )
        session.add(record)
        return {"score": None}

    total_score = data.get("total_score")
    reason = data.get("reason", "")

    record = StudentAnswerRecord(
        task_id=task_id,
        question_id=question.question_id,
        student_id=student_id,
        user_answer=student_answer,
        score=float(total_score) if total_score is not None else 0,
        is_correct=1 if total_score is not None and total_score >= 6.0 else 0,
        ai_score=float(total_score) if total_score is not None else None,
        judge_reason=reason,
    )
    session.add(record)
    return {"score": total_score}


# ===== 创建/发布/关闭任务 =====

class QuestionItem(BaseModel):
    """任务中的单题。"""
    id: int
    type: str = "single_choice"
    stem: str = ""
    options: list[dict[str, str]] | None = None
    answer: str = ""
    answerList: list[str] | None = None
    explanation: str | None = None
    knowledgePoint: str | None = None
    difficulty: str = "medium"
    score: float = 0


class SaveAnswerTaskRequest(BaseModel):
    """创建/保存答题任务。"""
    title: str
    courseId: int
    courseName: str = ""
    classId: int = 0
    className: str = ""
    teacherName: str = ""
    knowledgePoints: list[str] = []
    status: str = "draft"
    questions: list[QuestionItem] = []


def _ensure_question_in_bank(session: Session, item: QuestionItem, course_id: int) -> int:
    """确保题目在题库中（不存在则创建），返回 question_id。"""
    # 按题干查重
    existing = session.exec(
        select(AiQuestion).where(
            AiQuestion.course_id == course_id,
            AiQuestion.content == item.stem,
        )
    ).first()
    if existing:
        return existing.question_id

    # 找/建知识点
    point_id = 0
    kp_name = item.knowledgePoint or "综合"
    module = session.exec(
        select(KnowledgeModule)
        .where(KnowledgeModule.course_id == course_id)
        .limit(1)
    ).first()
    if not module:
        module = KnowledgeModule(course_id=course_id, module_name="默认模块")
        session.add(module)
        session.commit()
        session.refresh(module)

    kp = session.exec(
        select(KnowledgePoint)
        .where(KnowledgePoint.module_id == module.module_id, KnowledgePoint.point_name == kp_name)
    ).first()
    if not kp:
        kp = KnowledgePoint(module_id=module.module_id, point_name=kp_name)
        session.add(kp)
        session.commit()
        session.refresh(kp)
    point_id = kp.point_id

    import json
    type_map = {"single_choice": 1, "multi_choice": 2, "judge": 3, "fill_blank": 4, "short_answer": 5}
    answer = item.answer
    if item.answerList:
        answer = ",".join(item.answerList)

    q = AiQuestion(
        course_id=course_id,
        point_id=point_id,
        type=type_map.get(item.type, 1),
        content=item.stem,
        options=json.dumps(item.options, ensure_ascii=False) if item.options else None,
        correct_answer=answer,
        analysis=item.explanation,
        create_by=1,
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return q.question_id


@router.post("/answer-tasks", tags=["答题管理"])
def create_answer_task(
    req: SaveAnswerTaskRequest,
    session: Session = Depends(get_session),
) -> dict:
    """创建/保存答题任务。

    status='draft' 时存为草稿（status=0），'published' 时直接发布（status=1）。
    """
    status_int = 1 if req.status == "published" else 0
    deadline = datetime.now() + timedelta(days=7)

    task = AnswerTask(
        course_id=req.courseId,
        task_name=req.title,
        deadline=deadline,
        status=status_int,
        create_by=1,
    )
    if status_int == 1:
        task.publish_time = datetime.now()
    session.add(task)
    session.commit()
    session.refresh(task)

    # 关联题目
    for idx, item in enumerate(req.questions):
        qid = _ensure_question_in_bank(session, item, req.courseId)
        link = TaskQuestion(task_id=task.task_id, question_id=qid, sort_num=idx)
        session.add(link)
    session.commit()

    # 返回符合 QuizAssignmentRecord 的结构
    return {
        "id": task.task_id,
        "title": task.task_name,
        "courseId": task.course_id,
        "courseName": req.courseName,
        "classId": req.classId,
        "className": req.className,
        "teacherName": req.teacherName,
        "knowledgePoints": req.knowledgePoints,
        "questionCount": len(req.questions),
        "totalScore": 100,
        "status": req.status,
        "publishTime": task.publish_time.strftime("%Y-%m-%d %H:%M") if task.publish_time else "",
        "deadline": deadline.strftime("%Y-%m-%d %H:%M"),
    }


@router.post("/answer-tasks/{task_id}/publish", tags=["答题管理"])
def publish_answer_task(
    task_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """发布答题任务（status → 1）。"""
    task = session.get(AnswerTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = 1
    task.publish_time = datetime.now()
    session.add(task)
    session.commit()
    return {"id": task.task_id, "status": "published", "message": "已发布"}


@router.post("/answer-tasks/{task_id}/close", tags=["答题管理"])
def close_answer_task(
    task_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """关闭答题任务（status → 2）。"""
    task = session.get(AnswerTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = 2
    session.add(task)
    session.commit()
    return {"id": task.task_id, "status": "closed", "message": "已关闭"}


# ===== AI 生成题目（代理算法服务 8001）=====

def _retrieve_reference_questions(
    session: Session,
    course_id: int,
    knowledge_points: list[str],
    difficulty: str,
    top_k: int = 5,
) -> list[dict]:
    """从题库按知识点+难度检索相似题作为 RAG 参考样本。

    检索策略：
        1. 按知识点名称匹配 KnowledgePoint → 拿 point_id 列表
        2. 查 AiQuestion：course_id + point_id IN (...) + difficulty
        3. 不足时跨知识点补充（同课程任意知识点，同难度）
    返回：[{type, stem, options, answer, explanation, knowledge_point, difficulty}]
    """
    import json as _json

    # 步骤 1：按知识点名称找 point_id
    point_ids: list[int] = []
    if knowledge_points:
        kps = session.exec(
            select(KnowledgePoint)
            .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
            .where(
                KnowledgeModule.course_id == course_id,
                KnowledgePoint.point_name.in_(knowledge_points),
            )
        ).all()
        point_ids = [kp.point_id for kp in kps]

    # 步骤 2：精确匹配（知识点 + 难度）
    matched: list[AiQuestion] = []
    if point_ids:
        matched = list(session.exec(
            select(AiQuestion).where(
                AiQuestion.course_id == course_id,
                AiQuestion.point_id.in_(point_ids),
                AiQuestion.difficulty == difficulty,
            ).limit(top_k)
        ).all())

    # 步骤 3：不足时跨知识点补充（同课程，同难度）
    if len(matched) < top_k:
        existing_ids = {q.question_id for q in matched}
        extra = list(session.exec(
            select(AiQuestion).where(
                AiQuestion.course_id == course_id,
                AiQuestion.difficulty == difficulty,
                ~AiQuestion.question_id.in_(existing_ids) if existing_ids else True,
            ).limit(top_k - len(matched))
        ).all())
        matched.extend(extra)

    # 组装返回
    result = []
    for q in matched[:top_k]:
        kp = session.get(KnowledgePoint, q.point_id)
        # 解析 options
        options_text = ""
        if q.options:
            try:
                opts = _json.loads(q.options)
                options_text = "；".join(opts) if isinstance(opts, list) else str(opts)
            except (ValueError, TypeError):
                options_text = q.options or ""
        result.append({
            "type": _TYPE_MAP.get(q.type, "single_choice"),
            "stem": q.content,
            "options": options_text,
            "answer": q.correct_answer,
            "explanation": q.analysis or "",
            "knowledge_point": kp.point_name if kp else "",
            "difficulty": q.difficulty or "medium",
        })
    return result


class GenerateExercisesRequest(BaseModel):
    """前端 → 后端的生成请求。"""
    courseId: int
    knowledgePoints: list[str] = []
    questionTypes: list[str] = []
    questionCount: int = 5
    difficulty: str = "medium"
    extraRequirements: str = ""


@router.post("/exercises/generate", tags=["AI 出题"])
def generate_exercises_proxy(
    req: GenerateExercisesRequest,
    session: Session = Depends(get_session),
) -> dict:
    """代理调用算法服务 8001 的 /generate_exercises。

    将响应转换为前端 QuizQuestion[] 格式。
    """
    # 查课程名
    course = session.get(Course, req.courseId)
    course_name = course.course_name if course else "未知课程"

    # 按题型分布：均匀分配
    type_map = {"single_choice": 0, "multi_choice": 0, "judge": 0, "fill_blank": 0, "short_answer": 0}
    types = req.questionTypes or ["single_choice"]
    for i in range(req.questionCount):
        t = types[i % len(types)]
        if t in type_map:
            type_map[t] += 1

    # RAG 检索：从题库拉参考题注入 prompt（题库为空时返回空列表，算法服务回退纯 LLM）
    reference_questions = _retrieve_reference_questions(
        session, req.courseId, req.knowledgePoints or [], req.difficulty
    )

    payload = {
        "course_id": req.courseId,
        "course_name": course_name,
        "knowledge_points": req.knowledgePoints or ["综合"],
        "difficulty": req.difficulty,
        "extra_requirements": req.extraRequirements,
        "question_types": type_map,
        "reference_questions": reference_questions,
    }

    try:
        resp = httpx.post(
            "http://127.0.0.1:8001/generate_exercises",
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI 算法服务未启动（8001 端口）")
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200] if e.response.text else "AI 服务错误"
        raise HTTPException(status_code=503, detail=f"AI 服务错误: {detail}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"算法服务不可达: {e}")

    # 转换为前端 QuizQuestion 格式
    questions = []
    raw_questions = data.get("questions", [])
    for idx, q in enumerate(raw_questions):
        questions.append({
            "id": -(idx + 1),  # 负数 ID 标记为未入库
            "courseId": req.courseId,
            "type": q.get("type", "single_choice"),
            "stem": q.get("stem", ""),
            "options": q.get("options"),
            "answer": q.get("answer", ""),
            "answerList": q.get("answer_list"),
            "explanation": q.get("explanation", ""),
            "difficulty": q.get("difficulty", req.difficulty),
            "knowledgePoint": q.get("knowledge_point", ""),
            "score": round(100.0 / max(len(raw_questions), 1), 1),
            "status": "draft",
            "source": "ai",
        })

    meta_raw = data.get("meta", {})
    return {
        "questions": questions,
        "meta": {
            "model": meta_raw.get("model", "unknown"),
            "elapsedMs": meta_raw.get("elapsed_ms", 0),
        },
    }
