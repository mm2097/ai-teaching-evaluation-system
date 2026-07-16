"""答题任务与记录 API。

接口：
    GET  /api/v1/answer-tasks              答题任务列表（教师视角）
    POST /api/v1/answer-tasks              创建/保存答题任务
    POST /api/v1/answer-tasks/{id}/publish 发布任务
    POST /api/v1/answer-tasks/{id}/close   关闭任务
    GET  /api/v1/answer-records            答题记录列表（按任务/学生聚合）
    POST /api/v1/self-practice/start        学生创建自主练习
    POST /api/v1/self-practice/submit       学生提交自主练习
    POST /api/v1/exercises/generate        AI 生成题目（代理算法服务）
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, func, select

from app.core.config import settings
from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    AiQuestion,
    AiGenerationLog,
    AnswerTask,
    AnswerTaskClass,
    ClassInfo,
    Course,
    CourseStudent,
    KnowledgeModule,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
    SysRole,
    SysUser,
    TaskQuestion,
    Teacher,
)
from app.models.question import TASK_TYPE_ASSIGNMENT, TASK_TYPE_SELF_PRACTICE
from app.services.mastery import refresh_student_mastery
from app.services.question_answers import (
    answer_for_response,
    encode_correct_answer,
    judge_objective_answer,
)

router = APIRouter()

# status 映射：DB int → 前端 string
_STATUS_MAP = {0: "draft", 1: "published", 2: "closed"}
_TYPE_MAP = {1: "single_choice", 2: "multi_choice", 3: "judge", 4: "fill_blank", 5: "short_answer"}
_SELF_PRACTICE_PREFIX = "【自主练习】"


def _role_code(current_user: SysUser, session: Session) -> str:
    role = session.get(SysRole, current_user.role_id)
    if not role:
        raise HTTPException(status_code=403, detail="用户角色无效")
    return role.role_code


def _student_for_user(current_user: SysUser, session: Session) -> Student | None:
    return session.exec(
        select(Student).where(Student.user_id == current_user.user_id)
    ).first()


def _teacher_for_user(current_user: SysUser, session: Session) -> Teacher | None:
    return session.exec(
        select(Teacher).where(Teacher.user_id == current_user.user_id)
    ).first()


def _can_access_course(current_user: SysUser, course_id: int, session: Session) -> bool:
    role_code = _role_code(current_user, session)
    if role_code == "admin":
        return True
    if role_code == "teacher":
        teacher = _teacher_for_user(current_user, session)
        course = session.get(Course, course_id)
        return bool(teacher and course and course.teacher_id == teacher.teacher_id)
    if role_code == "student":
        student = _student_for_user(current_user, session)
        if not student:
            return False
        enrollment = session.exec(
            select(CourseStudent).where(
                CourseStudent.course_id == course_id,
                CourseStudent.student_id == student.student_id,
            )
        ).first()
        return enrollment is not None
    return False


def _require_course_access(current_user: SysUser, course_id: int, session: Session) -> None:
    if not _can_access_course(current_user, course_id, session):
        raise HTTPException(status_code=403, detail="无权访问该课程")


def _task_class_id(task_id: int, session: Session) -> int | None:
    link = session.exec(
        select(AnswerTaskClass).where(AnswerTaskClass.task_id == task_id)
    ).first()
    return link.class_id if link else None


def _is_self_practice(task: AnswerTask) -> bool:
    return task.task_type == TASK_TYPE_SELF_PRACTICE


def _parse_question_options(raw: str | None) -> list[dict[str, str]]:
    """Normalize legacy string options and current object options for the frontend."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []

    options: list[dict[str, str]] = []
    for index, item in enumerate(parsed):
        fallback_key = chr(ord("A") + index)
        if isinstance(item, dict):
            key = str(item.get("key") or fallback_key)
            text = str(item.get("text") or "")
        else:
            value = str(item)
            match = re.match(r"^\s*([A-Za-z])\s*[.、．:]\s*(.*)$", value)
            key = match.group(1).upper() if match else fallback_key
            text = match.group(2) if match else value
        options.append({"key": key, "text": text})
    return options


def _serialize_question(
    question: AiQuestion,
    session: Session,
    score: float,
    include_solution: bool = True,
) -> dict[str, Any]:
    knowledge_point = session.get(KnowledgePoint, question.point_id)
    answer, answer_list = answer_for_response(question.type, question.correct_answer)
    return {
        "id": question.question_id,
        "stem": question.content,
        "type": _TYPE_MAP.get(question.type, "single_choice"),
        "knowledgePoint": knowledge_point.point_name if knowledge_point else "",
        "score": round(score, 1),
        "options": _parse_question_options(question.options),
        "answer": answer if include_solution else "",
        "answerList": answer_list if include_solution else None,
        "explanation": question.analysis or "" if include_solution else "",
        "difficulty": question.difficulty or "medium",
    }


@router.get("/answer-tasks", tags=["答题管理"])
def list_answer_tasks(
    course_id: int | None = Query(default=None),
    teacher_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """答题任务列表（含题目数、总分、课程/班级名称）。"""
    role_code = _role_code(current_user, session)
    if role_code == "teacher":
        teacher = _teacher_for_user(current_user, session)
        if not teacher:
            raise HTTPException(status_code=403, detail="教师信息不存在")
        teacher_id = teacher.teacher_id
    elif role_code == "student":
        teacher_id = None

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
    current_student = _student_for_user(current_user, session) if role_code == "student" else None

    # 学生视角：批量查询已提交状态
    student_submissions: dict[int, dict] = {}
    if role_code == "student" and current_student:
        task_ids = [t.task_id for t in tasks]
        if task_ids:
            submission_rows = session.exec(
                select(StudentAnswerRecord).where(
                    StudentAnswerRecord.task_id.in_(task_ids),
                    StudentAnswerRecord.student_id == current_student.student_id,
                )
            ).all()
            for row in submission_rows:
                if row.task_id not in student_submissions:
                    student_submissions[row.task_id] = {
                        "submitted": True,
                        "myScore": 0.0,
                        "mySubmissionId": row.answer_id,
                    }
                student_submissions[row.task_id]["myScore"] += float(row.score)

    result = []
    for t in tasks:
        if not _can_access_course(current_user, t.course_id, session):
            continue
        if role_code != "student" and _is_self_practice(t):
            continue
        if role_code == "student":
            if t.status == 0:
                continue  # 草稿不可见
            if t.status == 2:
                # 已关闭的任务仅当学生已提交且教师允许查看详情时可见
                sub = student_submissions.get(t.task_id)
                if not sub or not t.allow_review:
                    continue
            # status=1: 正常显示（含已截止）
            if _is_self_practice(t) and t.create_by != current_user.user_id:
                continue
            target_class_id = _task_class_id(t.task_id, session)
            if target_class_id and (
                not current_student or current_student.class_id != target_class_id
            ):
                continue
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
        for tq, q in tq_rows:
            score = 100.0 / max(len(tq_rows), 1)  # 均分
            total_score += score
            questions.append(
                _serialize_question(
                    q,
                    session,
                    score,
                    include_solution=role_code != "student",
                )
            )

        class_id = _task_class_id(t.task_id, session) or 0
        cls = session.get(ClassInfo, class_id) if class_id else None
        class_name = cls.class_name if cls else ""

        # 学生视角标注答题状态
        submission_info = student_submissions.get(t.task_id) if role_code == "student" else None
        task_dict = {
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
            "maxAttempts": t.max_attempts,
            "allowReview": bool(t.allow_review),
            "questions": questions,
        }
        if submission_info:
            task_dict["submitted"] = True
            task_dict["myScore"] = round(submission_info["myScore"], 1)
            task_dict["mySubmissionId"] = submission_info["mySubmissionId"]
        else:
            task_dict["submitted"] = False
        result.append(task_dict)

    return result


@router.get("/answer-records", tags=["答题管理"])
def list_answer_records(
    task_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
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

    role_code = _role_code(current_user, session)
    current_student = _student_for_user(current_user, session) if role_code == "student" else None
    result = []
    for (tid, sid), records in grouped.items():
        stu = session.get(Student, sid)
        task = session.get(AnswerTask, tid)
        if not task or not _can_access_course(current_user, task.course_id, session):
            continue
        if role_code != "student" and _is_self_practice(task):
            continue
        if role_code == "student" and (not current_student or sid != current_student.student_id):
            continue

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


@router.get("/answer-records/{submission_id}", tags=["答题管理"])
def get_answer_record_detail(
    submission_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Return one submission with per-question answers and grading details."""
    first_record = session.get(StudentAnswerRecord, submission_id)
    if not first_record:
        raise HTTPException(status_code=404, detail="答题记录不存在")
    task = session.get(AnswerTask, first_record.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="答题任务不存在")
    _require_course_access(current_user, task.course_id, session)
    role_code = _role_code(current_user, session)
    if role_code != "student" and _is_self_practice(task):
        raise HTTPException(status_code=403, detail="自主练习记录仅学生本人可见")
    if role_code == "student":
        current_student = _student_for_user(current_user, session)
        if not current_student or first_record.student_id != current_student.student_id:
            raise HTTPException(status_code=403, detail="无权查看该答题记录")
        # 尊重教师设置的"是否允许交卷后查看详情"
        if not task.allow_review:
            raise HTTPException(status_code=403, detail="教师已关闭本题答题详情查看权限")

    records = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == first_record.task_id,
            StudentAnswerRecord.student_id == first_record.student_id,
        )
    ).all()
    records_by_question = {record.question_id: record for record in records}
    task_questions = session.exec(
        select(TaskQuestion, AiQuestion)
        .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
        .where(TaskQuestion.task_id == first_record.task_id)
        .order_by(TaskQuestion.sort_num)
    ).all()
    per_score = 100.0 / max(len(task_questions), 1)

    question_results = []
    for _, question in task_questions:
        record = records_by_question.get(question.question_id)
        manual_required = bool(
            question.type == 5 and record and record.ai_score is None
        )
        question_results.append({
            "question": _serialize_question(question, session, per_score),
            "userAnswer": record.user_answer if record else "",
            "isCorrect": bool(record.is_correct) if record else False,
            "manualRequired": manual_required,
            "aiScore": record.ai_score if record else None,
            "aiReason": record.judge_reason if record else "",
        })

    return {
        "submissionId": submission_id,
        "taskId": first_record.task_id,
        "studentId": first_record.student_id,
        "score": round(sum(float(record.score) for record in records), 1),
        "totalScore": 100,
        "questionResults": question_results,
    }


class SubmitAnswersRequest(BaseModel):
    """学生提交答题。"""

    task_id: int
    answers: dict[str, str] = Field(default_factory=dict)  # {question_id: student_answer}
    student_id: int = 1  # 默认 1（MVP 无登录态时的兜底）


@router.post("/answer-records", tags=["答题管理"])
def submit_answers(
    req: SubmitAnswersRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """学生提交答题答案。

    客观题（type 1-4）：规则判分
    简答题（type 5）：调算法服务 8001 AI 判分
    """
    task = session.get(AnswerTask, req.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    _require_course_access(current_user, task.course_id, session)
    if _role_code(current_user, session) != "student":
        raise HTTPException(status_code=403, detail="只有学生可以提交答案")
    if _is_self_practice(task):
        raise HTTPException(status_code=409, detail="自主练习请使用专用提交接口")
    if task.status != 1:
        raise HTTPException(status_code=409, detail="任务当前不可提交")
    if task.deadline < datetime.now():
        raise HTTPException(status_code=409, detail="任务已截止")

    current_student = _student_for_user(current_user, session)
    if not current_student:
        raise HTTPException(status_code=403, detail="学生信息不存在")
    target_class_id = _task_class_id(task.task_id, session)
    if target_class_id and current_student.class_id != target_class_id:
        raise HTTPException(status_code=403, detail="该任务未分配给学生所在班级")
    req.student_id = current_student.student_id

    result = _grade_task_answers(
        task=task,
        student=current_student,
        answers=req.answers,
        session=session,
    )
    session.commit()
    return result


def _grade_task_answers(
    task: AnswerTask,
    student: Student,
    answers: dict[str, str],
    session: Session,
) -> dict:
    """判分并写入答题记录，由调用方统一提交事务。"""
    tq_rows = session.exec(
        select(TaskQuestion, AiQuestion)
        .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
        .where(TaskQuestion.task_id == task.task_id)
        .order_by(TaskQuestion.sort_num)
    ).all()

    if not tq_rows:
        raise HTTPException(status_code=404, detail="任务不存在或无题目")

    # 检查是否已提交过（当前为单次答题模式，后续扩展多次答题时需改造此处逻辑）
    previous_records = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == student.student_id,
        )
    ).all()
    if previous_records and task.max_attempts <= 1:
        raise HTTPException(
            status_code=409,
            detail="你已完成该答题任务，不可重复作答",
        )
    # 多次答题模式下删除旧记录后允许重新提交
    for record in previous_records:
        session.delete(record)
    if previous_records:
        session.flush()

    total_score = 0.0
    correct_count = 0
    manual_question_ids: list[int] = []

    for _, question in tq_rows:
        qid = str(question.question_id)
        user_answer = answers.get(qid, "")
        per_score = 100.0 / max(len(tq_rows), 1)

        if question.type == 5:
            # 简答题：调 AI 判分
            ai_result = _call_ai_judge(
                session,
                question,
                user_answer,
                student.student_id,
                task.task_id,
                per_score,
            )
            if ai_result["score"] is not None:
                total_score += ai_result["score"] * per_score / 10.0  # AI 给 0-10 分，映射到 per_score
                if ai_result["score"] >= 6.0:
                    correct_count += 1
            if ai_result["manual_required"]:
                manual_question_ids.append(question.question_id)
        else:
            # 客观题：规则判分
            is_correct = _judge_objective(question, user_answer)
            score = per_score if is_correct else 0
            record = StudentAnswerRecord(
                task_id=task.task_id,
                question_id=question.question_id,
                student_id=student.student_id,
                user_answer=user_answer,
                score=score,
                is_correct=1 if is_correct else 0,
            )
            session.add(record)
            total_score += score
            if is_correct:
                correct_count += 1

    session.flush()

    first_record = session.exec(
        select(StudentAnswerRecord)
        .where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == student.student_id,
        )
        .order_by(StudentAnswerRecord.answer_id)
    ).first()
    if not first_record:
        raise HTTPException(status_code=500, detail="答题记录保存失败")

    records = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == student.student_id,
        )
    ).all()
    refresh_student_mastery(session, student.student_id, task.course_id)
    records_by_question = {record.question_id: record for record in records}
    question_results = []
    for _, question in tq_rows:
        record = records_by_question.get(question.question_id)
        manual_required = bool(question.type == 5 and record and record.ai_score is None)
        question_results.append({
            "question": _serialize_question(question, session, per_score),
            "userAnswer": record.user_answer if record else "",
            "isCorrect": bool(record.is_correct) if record else False,
            "manualRequired": manual_required,
            "aiScore": record.ai_score if record else None,
            "aiReason": record.judge_reason if record else "",
        })

    return {
        "submissionId": first_record.answer_id,
        "score": round(total_score, 1),
        "totalScore": 100,
        "correctCount": correct_count,
        "manualRequiredCount": len(manual_question_ids),
        "manualQuestionIds": manual_question_ids,
        "questionResults": question_results,
    }


def _judge_objective(question: AiQuestion, user_answer: str) -> bool:
    """客观题规则判分。"""
    return judge_objective_answer(question.type, question.correct_answer, user_answer)


def _call_ai_judge(
    session: Session,
    question: AiQuestion,
    student_answer: str,
    student_id: int,
    task_id: int,
    question_max_score: float,
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
    except (httpx.HTTPError, ValueError):
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
        return {"score": None, "manual_required": True}

    if not isinstance(data, dict):
        data = {}
    raw_score = data.get("total_score")
    reason = str(data.get("reason") or "")
    manual_required = data.get("flag") == "manual_required" or raw_score is None

    if not manual_required:
        try:
            total_score = max(0.0, min(10.0, float(raw_score)))
        except (TypeError, ValueError):
            total_score = None
            manual_required = True
            reason = reason or "AI 返回的分数无效，需人工判分"
    else:
        total_score = None

    if manual_required and not reason:
        reason = "AI 未返回有效分数，需人工判分"

    scaled_score = (
        total_score * question_max_score / 10.0
        if total_score is not None
        else 0
    )
    record = StudentAnswerRecord(
        task_id=task_id,
        question_id=question.question_id,
        student_id=student_id,
        user_answer=student_answer,
        score=scaled_score,
        is_correct=1 if total_score is not None and total_score >= 6.0 else 0,
        ai_score=float(total_score) if total_score is not None else None,
        judge_reason=reason,
    )
    session.add(record)
    return {"score": total_score, "manual_required": manual_required}


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


class SelfPracticeSubmitRequest(BaseModel):
    """学生自主练习提交参数；标准答案只从服务端已保存题目读取。"""

    taskId: int
    answers: dict[str, str] = Field(default_factory=dict)


class SaveAnswerTaskRequest(BaseModel):
    """创建/保存答题任务。"""
    title: str
    courseId: int
    courseName: str = ""
    classId: int = 0
    className: str = ""
    teacherName: str = ""
    knowledgePoints: list[str] = Field(default_factory=list)
    status: str = "draft"
    questions: list[QuestionItem] = Field(default_factory=list)
    deadline: str = ""  # 截止时间字符串，如 "2026-07-20 23:59"，为空则默认7天后


def _ensure_question_in_bank(
    session: Session,
    item: QuestionItem,
    course_id: int,
    creator_id: int,
) -> int:
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
        session.flush()

    kp = session.exec(
        select(KnowledgePoint)
        .where(KnowledgePoint.module_id == module.module_id, KnowledgePoint.point_name == kp_name)
    ).first()
    if not kp:
        kp = KnowledgePoint(module_id=module.module_id, point_name=kp_name)
        session.add(kp)
        session.flush()
    point_id = kp.point_id

    type_map = {"single_choice": 1, "multi_choice": 2, "judge": 3, "fill_blank": 4, "short_answer": 5}
    answer = encode_correct_answer(item.type, item.answer, item.answerList)

    q = AiQuestion(
        course_id=course_id,
        point_id=point_id,
        type=type_map.get(item.type, 1),
        content=item.stem,
        options=json.dumps(item.options, ensure_ascii=False) if item.options else None,
        correct_answer=answer,
        analysis=item.explanation,
        create_by=creator_id,
    )
    session.add(q)
    session.flush()
    return q.question_id


@router.post("/self-practice/submit", tags=["答题管理"])
def submit_self_practice(
    req: SelfPracticeSubmitRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """提交已创建的自主练习，客户端不能传入或修改标准答案。"""
    if _role_code(current_user, session) != "student":
        raise HTTPException(status_code=403, detail="只有学生可以提交自主练习")

    student = _student_for_user(current_user, session)
    if not student:
        raise HTTPException(status_code=403, detail="学生信息不存在")

    task = session.get(AnswerTask, req.taskId)
    if not task or not _is_self_practice(task):
        raise HTTPException(status_code=404, detail="自主练习不存在")
    if task.create_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权提交他人的自主练习")
    _require_course_access(current_user, task.course_id, session)
    if task.status != 1:
        raise HTTPException(status_code=409, detail="自主练习已提交或已关闭")
    if task.deadline < datetime.now():
        raise HTTPException(status_code=409, detail="自主练习已过期")

    question_ids = set(session.exec(
        select(TaskQuestion.question_id).where(TaskQuestion.task_id == task.task_id)
    ).all())
    if not question_ids:
        raise HTTPException(status_code=404, detail="自主练习没有题目")
    valid_answer_keys = {str(question_id) for question_id in question_ids}
    unknown_answer_keys = set(req.answers) - valid_answer_keys
    if unknown_answer_keys:
        raise HTTPException(status_code=422, detail="答案中包含不存在的题目 ID")

    try:
        result = _grade_task_answers(
            task=task,
            student=student,
            answers=req.answers,
            session=session,
        )
        task.status = 2
        session.add(task)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        **result,
        "taskId": task.task_id,
        "taskTitle": task.task_name,
    }


@router.post("/answer-tasks", tags=["答题管理"])
def create_answer_task(
    req: SaveAnswerTaskRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """创建/保存答题任务。

    status='draft' 时存为草稿（status=0），'published' 时直接发布（status=1）。
    """
    course = session.get(Course, req.courseId)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    _require_course_access(current_user, req.courseId, session)

    role_code = _role_code(current_user, session)
    if role_code not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="无权创建答题任务")
    if req.title.startswith(_SELF_PRACTICE_PREFIX):
        raise HTTPException(status_code=422, detail="自主练习标题为系统保留格式")

    target_class_id = req.classId
    if target_class_id and not session.get(ClassInfo, target_class_id):
        raise HTTPException(status_code=404, detail="班级不存在")

    status_int = 1 if req.status == "published" else 0
    # 解析截止时间，为空则默认7天后
    if req.deadline:
        try:
            deadline = datetime.strptime(req.deadline, "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                deadline = datetime.strptime(req.deadline, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                deadline = datetime.now() + timedelta(days=7)
    else:
        deadline = datetime.now() + timedelta(days=7)

    task = AnswerTask(
        course_id=req.courseId,
        task_name=req.title,
        task_type=TASK_TYPE_ASSIGNMENT,
        deadline=deadline,
        status=status_int,
        create_by=current_user.user_id,
    )
    if status_int == 1:
        task.publish_time = datetime.now()
    session.add(task)
    session.flush()
    if target_class_id:
        session.add(
            AnswerTaskClass(task_id=task.task_id, class_id=target_class_id)
        )

    # 关联题目
    for idx, item in enumerate(req.questions):
        qid = _ensure_question_in_bank(
            session,
            item,
            req.courseId,
            current_user.user_id,
        )
        link = TaskQuestion(task_id=task.task_id, question_id=qid, sort_num=idx)
        session.add(link)
    session.commit()
    session.refresh(task)

    # 返回符合 QuizAssignmentRecord 的结构
    return {
        "id": task.task_id,
        "title": task.task_name,
        "courseId": task.course_id,
        "courseName": req.courseName,
        "classId": target_class_id,
        "className": req.className if target_class_id else "",
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
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """发布答题任务（status → 1）。"""
    task = session.get(AnswerTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if _role_code(current_user, session) not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="无权发布答题任务")
    _require_course_access(current_user, task.course_id, session)
    task.status = 1
    task.publish_time = datetime.now()
    session.add(task)
    session.commit()
    return {"id": task.task_id, "status": "published", "message": "已发布"}


@router.post("/answer-tasks/{task_id}/close", tags=["答题管理"])
def close_answer_task(
    task_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """关闭答题任务（status → 2）。"""
    task = session.get(AnswerTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if _role_code(current_user, session) not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="无权关闭答题任务")
    _require_course_access(current_user, task.course_id, session)
    task.status = 2
    session.add(task)
    session.commit()
    return {"id": task.task_id, "status": "closed", "message": "已关闭"}


class ReopenAnswerTaskRequest(BaseModel):
    """重新开启/延长期限请求。"""
    deadline: str = ""  # 新的截止时间，为空则默认延后7天


@router.post("/answer-tasks/{task_id}/reopen", tags=["答题管理"])
def reopen_answer_task(
    task_id: int,
    req: ReopenAnswerTaskRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """重新开启已关闭/已截止的答题任务，可设置新的截止时间。"""
    task = session.get(AnswerTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if _role_code(current_user, session) not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="无权操作答题任务")
    _require_course_access(current_user, task.course_id, session)
    if task.status not in (1, 2):
        raise HTTPException(status_code=409, detail="仅已发布或已关闭的任务可重新开启")

    # 解析新的截止时间
    if req.deadline:
        try:
            new_deadline = datetime.strptime(req.deadline, "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                new_deadline = datetime.strptime(req.deadline, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                raise HTTPException(status_code=422, detail="截止时间格式不正确，请使用 YYYY-MM-DD HH:MM")
    else:
        new_deadline = datetime.now() + timedelta(days=7)

    task.status = 1
    task.publish_time = datetime.now()
    task.deadline = new_deadline
    session.add(task)
    session.commit()
    return {
        "id": task.task_id,
        "status": "published",
        "deadline": new_deadline.strftime("%Y-%m-%d %H:%M"),
        "message": "已重新开启",
    }


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
    knowledgePoints: list[str] = Field(default_factory=list)
    questionTypes: list[
        Literal["single_choice", "multi_choice", "judge", "fill_blank", "short_answer"]
    ] = Field(default_factory=list)
    questionCount: int = Field(default=5, ge=1, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    extraRequirements: str = ""


def _consume_ai_quota(
    req: GenerateExercisesRequest,
    session: Session,
    current_user: SysUser,
    operation: str,
) -> AiGenerationLog:
    """校验并预先记录一次 AI 调用，失败请求也占用额度以阻止成本绕过。"""
    role_code = _role_code(current_user, session)
    if role_code == "student":
        if req.questionCount > settings.AI_STUDENT_MAX_QUESTIONS:
            raise HTTPException(
                status_code=422,
                detail=f"学生自主练习单次最多生成 {settings.AI_STUDENT_MAX_QUESTIONS} 题",
            )
        daily_limit = settings.AI_STUDENT_DAILY_REQUEST_LIMIT
    else:
        daily_limit = settings.AI_STAFF_DAILY_REQUEST_LIMIT

    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    used = session.exec(
        select(func.count(AiGenerationLog.usage_id)).where(
            AiGenerationLog.user_id == current_user.user_id,
            AiGenerationLog.create_time >= day_start,
        )
    ).one()
    if used >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日 AI 出题额度已用完（{daily_limit} 次），请明天再试",
        )

    usage = AiGenerationLog(
        user_id=current_user.user_id,
        course_id=req.courseId,
        operation=operation,
        question_count=req.questionCount,
    )
    session.add(usage)
    session.commit()
    session.refresh(usage)
    return usage


@router.post("/exercises/generate", tags=["AI 出题"])
def generate_exercises_proxy(
    req: GenerateExercisesRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """教师/管理员代理调用算法服务 8001 的 /generate_exercises。"""
    if _role_code(current_user, session) not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="学生请使用自主练习接口")
    return _generate_exercises(
        req,
        session=session,
        current_user=current_user,
        operation="teacher_generate",
    )


def _generate_exercises(
    req: GenerateExercisesRequest,
    session: Session,
    current_user: SysUser,
    operation: str,
) -> dict:
    """校验配额后调用算法服务并转换为 QuizQuestion。

    将响应转换为前端 QuizQuestion[] 格式。
    """
    # 查课程名
    course = session.get(Course, req.courseId)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    _require_course_access(current_user, req.courseId, session)
    course_name = course.course_name
    usage = _consume_ai_quota(req, session, current_user, operation)

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
    except ValueError:
        raise HTTPException(status_code=503, detail="AI 服务返回了无效数据")

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
    usage.success = 1
    session.add(usage)
    session.commit()
    return {
        "questions": questions,
        "meta": {
            "model": meta_raw.get("model", "unknown"),
            "elapsedMs": meta_raw.get("elapsed_ms", 0),
        },
    }


@router.post("/self-practice/start", tags=["答题管理"])
def start_self_practice(
    req: GenerateExercisesRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """为当前学生生成并保存私人练习，返回不含标准答案的试卷。"""
    if _role_code(current_user, session) != "student":
        raise HTTPException(status_code=403, detail="只有学生可以创建自主练习")
    student = _student_for_user(current_user, session)
    if not student:
        raise HTTPException(status_code=403, detail="学生信息不存在")

    generated = _generate_exercises(
        req,
        session=session,
        current_user=current_user,
        operation="self_practice",
    )
    generated_questions = generated.get("questions", [])
    if not generated_questions:
        raise HTTPException(status_code=503, detail="未生成有效题目，请调整参数后重试")

    course = session.get(Course, req.courseId)
    now = datetime.now()
    task = AnswerTask(
        course_id=req.courseId,
        task_name=f"{_SELF_PRACTICE_PREFIX}{now.strftime('%Y-%m-%d %H:%M:%S')}",
        task_type=TASK_TYPE_SELF_PRACTICE,
        publish_time=now,
        deadline=now + timedelta(hours=1),
        status=1,
        create_by=current_user.user_id,
    )

    try:
        session.add(task)
        session.flush()
        persisted_question_ids: set[int] = set()
        for index, raw_question in enumerate(generated_questions):
            try:
                item = QuestionItem.model_validate(raw_question)
            except ValidationError as exc:
                raise HTTPException(status_code=503, detail="AI 返回的题目格式无效") from exc
            question_id = _ensure_question_in_bank(
                session,
                item,
                req.courseId,
                current_user.user_id,
            )
            if question_id in persisted_question_ids:
                raise HTTPException(status_code=422, detail="生成结果中包含重复题目")
            persisted_question_ids.add(question_id)
            session.add(
                TaskQuestion(
                    task_id=task.task_id,
                    question_id=question_id,
                    sort_num=index,
                )
            )
        session.flush()

        task_questions = session.exec(
            select(TaskQuestion, AiQuestion)
            .join(AiQuestion, TaskQuestion.question_id == AiQuestion.question_id)
            .where(TaskQuestion.task_id == task.task_id)
            .order_by(TaskQuestion.sort_num)
        ).all()
        per_score = 100.0 / len(task_questions)
        questions = [
            _serialize_question(question, session, per_score, include_solution=False)
            for _, question in task_questions
        ]
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "assignment": {
            "id": task.task_id,
            "title": task.task_name,
            "courseId": task.course_id,
            "courseName": course.course_name if course else "",
            "classId": student.class_id,
            "className": "",
            "teacherName": "",
            "knowledgePoints": list({
                question["knowledgePoint"]
                for question in questions
                if question["knowledgePoint"]
            }),
            "questionCount": len(questions),
            "totalScore": 100,
            "status": "published",
            "publishTime": task.publish_time.strftime("%Y-%m-%d %H:%M"),
            "deadline": task.deadline.strftime("%Y-%m-%d %H:%M"),
            "questions": questions,
        },
        "meta": generated["meta"],
    }
