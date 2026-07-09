"""答题任务与记录 API。

接口：
    GET /api/v1/answer-tasks    答题任务列表（教师视角）
    GET /api/v1/answer-records  答题记录列表（按任务/学生聚合）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.models import (
    AiQuestion,
    AnswerTask,
    ClassInfo,
    Course,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
    TaskQuestion,
    Teacher,
)

router = APIRouter()

# status 映射：DB int → 前端 string
_STATUS_MAP = {0: "draft", 1: "published", 2: "closed"}
_TYPE_MAP = {1: "single_choice", 2: "multi_choice", 3: "judge", 4: "fill_blank"}


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
                "difficulty": "medium",
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
