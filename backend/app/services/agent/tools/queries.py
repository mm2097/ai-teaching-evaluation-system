"""Agent A 学情问答工具集（10 个只读工具）。

每个工具签名统一为 (ctx: ToolContext, **kwargs) -> dict。
权限：course_id 必须在 ctx.course_id 范围内（前端注入）。
"""
from __future__ import annotations

import math
from typing import Any

from sqlmodel import func, select

from app.models import (
    AiQuestion,
    AttendanceRecord,
    ClassInfo,
    Course,
    CourseStudent,
    ExamBatch,
    InteractionRecord,
    KnowledgeMastery,
    KnowledgePoint,
    KnowledgeModule,
    ScoreRecord,
    Student,
    StudentAnswerRecord,
    StudyWarning,
)
from app.services.agent.registry import Tool, ToolRegistry
from app.services.mastery import accuracy_to_level, compute_class_mastery, compute_student_mastery


# ===== 辅助 =====

def _student_brief(student: Student) -> dict:
    return {
        "student_id": student.student_id,
        "name": student.real_name,
        "student_no": student.student_no,
    }


def _resolve_course_id(ctx, course_id: int | None) -> int | None:
    """解析 course_id：显式传 > ctx 注入。返回 None 表示无权限或缺失。"""
    cid = course_id or ctx.course_id
    return cid


# ===== 工具 1：课程总览 =====

def _t_get_course_overview(ctx, course_id: int = 0, **_) -> dict:
    """课程看板：学生数、均分、及格率、出勤率、预警数。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    course = ctx.session.get(Course, cid)
    if not course:
        return {"error": f"课程 {cid} 不存在"}

    # 学生数
    student_ids = ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all()

    # 最近一次考核成绩
    batches = ctx.session.exec(
        select(ExamBatch).where(ExamBatch.course_id == cid).order_by(ExamBatch.exam_time)
    ).all()
    avg_score = 0.0
    pass_rate = 0.0
    if batches:
        last = batches[-1]
        scores = ctx.session.exec(
            select(ScoreRecord.score).where(
                ScoreRecord.batch_id == last.batch_id,
                ScoreRecord.student_id.in_(student_ids),  # type: ignore
            )
        ).all()
        if scores:
            avg_score = round(sum(scores) / len(scores), 1)
            pass_rate = round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1)

    # 出勤率
    att_records = ctx.session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == cid,
            AttendanceRecord.student_id.in_(student_ids),  # type: ignore
        )
    ).all()
    attendance_rate = 0.0
    if att_records:
        present = sum(1 for r in att_records if r.status == 0)
        attendance_rate = round(present / len(att_records) * 100, 1)

    # 预警数
    warning_count = ctx.session.exec(
        select(func.count(StudyWarning.warning_id)).where(
            StudyWarning.course_id == cid,
            StudyWarning.handle_status == 0,
        )
    ).one()

    return {
        "course_id": cid,
        "course_name": course.course_name,
        "student_count": len(student_ids),
        "avg_score": avg_score,
        "pass_rate": pass_rate,
        "attendance_rate": attendance_rate,
        "warning_count": warning_count,
    }


# ===== 工具 2：成绩列表 =====

def _t_get_score_list(ctx, course_id: int = 0, assessment_id: int = 0, top_n: int = 0, **_) -> dict:
    """某次考核的成绩列表（可排序）。assessment_id=0 表示最近一次。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    batches = ctx.session.exec(
        select(ExamBatch).where(ExamBatch.course_id == cid).order_by(ExamBatch.exam_time)
    ).all()
    if not batches:
        return {"assessment": None, "scores": []}

    target = None
    if assessment_id:
        for b in batches:
            if b.batch_id == assessment_id:
                target = b
                break
    else:
        target = batches[-1]

    rows = ctx.session.exec(
        select(ScoreRecord, Student)
        .join(Student, ScoreRecord.student_id == Student.student_id)
        .where(ScoreRecord.batch_id == target.batch_id)
        .order_by(ScoreRecord.score.desc())
    ).all()

    student_ids = set(ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all())

    scores = []
    for rank, (sr, stu) in enumerate(rows, 1):
        if stu.student_id not in student_ids:
            continue
        scores.append({
            "rank": rank,
            "student_id": stu.student_id,
            "name": stu.real_name,
            "score": round(float(sr.score), 1),
        })
        if top_n and rank >= top_n:
            break

    return {"assessment": target.batch_name, "scores": scores}


# ===== 工具 3：成绩趋势 =====

def _t_get_score_trend(ctx, course_id: int = 0, student_id: int = 0, **_) -> dict:
    """班级整体或个人的成绩趋势（按批次时间排序）。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    batches = ctx.session.exec(
        select(ExamBatch).where(ExamBatch.course_id == cid).order_by(ExamBatch.exam_time)
    ).all()
    if not batches:
        return {"trend": []}

    student_ids = set(ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all())

    if student_id:
        # 个人趋势
        trend = []
        for b in batches:
            sr = ctx.session.exec(
                select(ScoreRecord).where(
                    ScoreRecord.batch_id == b.batch_id,
                    ScoreRecord.student_id == student_id,
                )
            ).first()
            trend.append({
                "assessment": b.batch_name,
                "score": round(float(sr.score), 1) if sr else None,
            })
        return {"scope": "student", "student_id": student_id, "trend": trend}

    # 班级趋势
    trend = []
    for b in batches:
        scores = ctx.session.exec(
            select(ScoreRecord.score).where(
                ScoreRecord.batch_id == b.batch_id,
                ScoreRecord.student_id.in_(student_ids),  # type: ignore
            )
        ).all()
        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        trend.append({"assessment": b.batch_name, "avg_score": avg, "count": len(scores)})
    return {"scope": "class", "trend": trend}


# ===== 工具 4：考勤 =====

def _t_get_attendance(ctx, course_id: int = 0, student_id: int = 0, **_) -> dict:
    """考勤统计：出勤率、缺勤日期列表。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    if student_id:
        records = ctx.session.exec(
            select(AttendanceRecord).where(
                AttendanceRecord.course_id == cid,
                AttendanceRecord.student_id == student_id,
            ).order_by(AttendanceRecord.attendance_date)
        ).all()
        if not records:
            return {"student_id": student_id, "rate": None, "absent_dates": []}
        present = sum(1 for r in records if r.status == 0)
        rate = round(present / len(records) * 100, 1)
        absent = [
            {"date": str(r.attendance_date), "status": _attendance_status_name(r.status)}
            for r in records if r.status != 0
        ]
        return {"student_id": student_id, "rate": rate, "absent_dates": absent}

    # 班级
    student_ids = set(ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all())
    records = ctx.session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == cid,
            AttendanceRecord.student_id.in_(student_ids),  # type: ignore
        )
    ).all()
    if not records:
        return {"scope": "class", "avg_rate": None}
    present = sum(1 for r in records if r.status == 0)
    avg_rate = round(present / len(records) * 100, 1)
    return {"scope": "class", "avg_rate": avg_rate, "total_records": len(records)}


def _attendance_status_name(status: int) -> str:
    return {0: "出勤", 1: "迟到", 2: "早退", 3: "缺勤", 4: "请假"}.get(status, "未知")


# ===== 工具 5：知识点掌握度 =====

def _t_get_knowledge_mastery(ctx, course_id: int = 0, student_id: int = 0, **_) -> dict:
    """知识点掌握度（按学生或班级）。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    if student_id:
        ms = compute_student_mastery(ctx.session, student_id, cid)
        return {
            "scope": "student",
            "student_id": student_id,
            "points": [
                {"point_name": m.point_name, "accuracy": m.accuracy, "level": m.level}
                for m in ms
            ],
        }

    ms = compute_class_mastery(ctx.session, cid)
    return {
        "scope": "class",
        "points": [
            {"point_name": m.point_name, "accuracy": m.accuracy, "level": m.level}
            for m in ms
        ],
    }


# ===== 工具 6：薄弱知识点 =====

def _t_get_weak_knowledge_points(ctx, course_id: int = 0, top_k: int = 5, **_) -> dict:
    """班级掌握度最低的 N 个知识点。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    ms = compute_class_mastery(ctx.session, cid)
    weak = sorted(ms, key=lambda m: m.accuracy)[:top_k]
    return {
        "weak_points": [
            {
                "point_name": m.point_name,
                "accuracy": m.accuracy,
                "level": m.level,
            }
            for m in weak
        ],
    }


# ===== 工具 7：预警学生 =====

def _t_get_warning_students(ctx, course_id: int = 0, **_) -> dict:
    """当前课程未处理的预警学生列表。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    warnings = ctx.session.exec(
        select(StudyWarning).where(
            StudyWarning.course_id == cid,
            StudyWarning.handle_status == 0,
        )
    ).all()

    grouped: dict[int, list[StudyWarning]] = {}
    for w in warnings:
        grouped.setdefault(w.student_id, []).append(w)

    out = []
    level_map = {1: "低", 2: "中", 3: "高"}
    for sid, ws in grouped.items():
        stu = ctx.session.get(Student, sid)
        max_level = max(w.warning_level for w in ws)
        out.append({
            "student_id": sid,
            "name": stu.real_name if stu else "",
            "level": level_map.get(max_level, "低"),
            "reasons": [w.warning_reason for w in ws],
        })

    out.sort(key=lambda x: {"高": 0, "中": 1, "低": 2}.get(x["level"], 3))
    return {"warning_students": out}


# ===== 工具 8：学生综合档案 =====

def _t_get_student_detail(ctx, course_id: int = 0, student_id: int = 0, **_) -> dict:
    """学生综合档案：成绩、考勤、掌握度、答题情况。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid or not student_id:
        return {"error": "需要 course_id 和 student_id"}

    stu = ctx.session.get(Student, student_id)
    if not stu:
        return {"error": f"学生 {student_id} 不存在"}

    # 成绩历史
    rows = ctx.session.exec(
        select(ScoreRecord, ExamBatch)
        .join(ExamBatch, ScoreRecord.batch_id == ExamBatch.batch_id)
        .where(ScoreRecord.student_id == student_id, ScoreRecord.course_id == cid)
        .order_by(ExamBatch.exam_time)
    ).all()
    scores = [{"assessment": eb.batch_name, "score": round(float(sr.score), 1)} for sr, eb in rows]

    # 考勤
    atts = ctx.session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.course_id == cid,
        )
    ).all()
    att_rate = round(sum(1 for r in atts if r.status == 0) / len(atts) * 100, 1) if atts else None

    # 掌握度
    masteries = compute_student_mastery(ctx.session, student_id, cid)
    weak = [m.point_name for m in masteries if m.accuracy < 60]
    strong = [m.point_name for m in masteries if m.accuracy >= 80]

    # 最近答题
    recent_answers = ctx.session.exec(
        select(StudentAnswerRecord, AiQuestion)
        .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
        .where(StudentAnswerRecord.student_id == student_id)
        .order_by(StudentAnswerRecord.submit_time.desc())
        .limit(10)
    ).all()
    answer_log = [
        {
            "is_correct": bool(a.is_correct),
            "content": (q.content[:60] + "...") if len(q.content) > 60 else q.content,
            "point_id": q.point_id,
        }
        for a, q in recent_answers
    ]

    return {
        "student_id": student_id,
        "name": stu.real_name,
        "student_no": stu.student_no,
        "scores": scores,
        "attendance_rate": att_rate,
        "weak_points": weak,
        "strong_points": strong,
        "recent_answers": answer_log,
    }


# ===== 工具 9：答题记录 =====

def _t_get_exercise_records(ctx, course_id: int = 0, student_id: int = 0, **_) -> dict:
    """答题记录（可按学生）。"""
    cid = _resolve_course_id(ctx, course_id)
    if not cid:
        return {"error": "未提供 course_id"}

    student_ids = set(ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all())

    stmt = (
        select(StudentAnswerRecord, AiQuestion, Student)
        .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
        .join(Student, StudentAnswerRecord.student_id == Student.student_id)
        .where(StudentAnswerRecord.student_id.in_(student_ids))  # type: ignore
    )
    if student_id:
        stmt = stmt.where(StudentAnswerRecord.student_id == student_id)
    stmt = stmt.order_by(StudentAnswerRecord.submit_time.desc()).limit(50)

    rows = ctx.session.exec(stmt).all()
    records = [
        {
            "student_id": stu.student_id,
            "name": stu.real_name,
            "is_correct": bool(a.is_correct),
            "content": (q.content[:60] + "...") if len(q.content) > 60 else q.content,
        }
        for a, q, stu in rows
    ]
    return {"records": records, "count": len(records)}


# ===== 工具 10：模糊搜索学生 =====

def _t_search_student(ctx, keyword: str = "", **_) -> dict:
    """按姓名或学号模糊搜索学生（限当前课程范围）。"""
    cid = ctx.course_id
    if not cid:
        return {"error": "未提供 course_id 上下文"}
    if not keyword or len(keyword) < 1:
        return {"students": []}

    student_ids = set(ctx.session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == cid)
    ).all())

    pattern = f"%{keyword}%"
    students = ctx.session.exec(
        select(Student).where(
            Student.student_id.in_(student_ids),  # type: ignore
            (Student.real_name.like(pattern)) | (Student.student_no.like(pattern)),
        )
    ).all()

    return {
        "students": [
            {
                "student_id": s.student_id,
                "name": s.real_name,
                "student_no": s.student_no,
            }
            for s in students
        ]
    }


# ===== 注册 =====

def register_query_tools(registry: ToolRegistry) -> None:
    """把 10 个查询工具注册到 registry。"""
    tools = [
        Tool(
            name="get_course_overview",
            description="查询某课程的总览数据：学生数、均分、及格率、出勤率、预警数。适合教师问'班里整体情况怎么样'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer", "description": "课程 ID，未传时取上下文"},
                },
            },
            handler=_t_get_course_overview,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_score_list",
            description="查询某次考核的成绩排名列表。可取前 N 名。适合'期中前 5 名是谁'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "assessment_id": {"type": "integer", "default": 0, "description": "考核批次 ID，0=最近一次"},
                    "top_n": {"type": "integer", "default": 0, "description": "取前 N 名，0=全部"},
                },
            },
            handler=_t_get_score_list,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_score_trend",
            description="查询成绩趋势（班级整体均分趋势，或指定学生的历次成绩）。适合'谁退步最大'、'最近三次作业趋势'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "student_id": {"type": "integer", "default": 0, "description": "0=班级整体，非 0=个人"},
                },
            },
            handler=_t_get_score_trend,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_attendance",
            description="查询考勤情况：班级整体出勤率或某学生的缺勤明细。适合'张三出勤怎么样'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "student_id": {"type": "integer", "default": 0},
                },
            },
            handler=_t_get_attendance,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_knowledge_mastery",
            description="查询知识点掌握度：班级整体或某学生每个知识点的正确率与等级。适合'红黑树大家掌握得怎么样'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "student_id": {"type": "integer", "default": 0},
                },
            },
            handler=_t_get_knowledge_mastery,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_weak_knowledge_points",
            description="查询班级掌握度最低的知识点（默认 Top 5）。适合'我们班哪个知识点最差'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "top_k": {"type": "integer", "default": 5},
                },
            },
            handler=_t_get_weak_knowledge_points,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_warning_students",
            description="查询当前课程的预警学生名单（含预警原因与等级）。适合'哪些同学被预警了'。",
            parameters={
                "type": "object",
                "properties": {"course_id": {"type": "integer"}},
            },
            handler=_t_get_warning_students,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_student_detail",
            description="查询某学生的综合档案：成绩历史、考勤、知识点掌握、最近答题记录。适合'张三最近怎么样'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "student_id": {"type": "integer"},
                },
                "required": ["student_id"],
            },
            handler=_t_get_student_detail,
            category="query",
            agent="both",
        ),
        Tool(
            name="get_exercise_records",
            description="查询学生的 AI 答题记录（可指定学生）。适合'最近答题情况'。",
            parameters={
                "type": "object",
                "properties": {
                    "course_id": {"type": "integer"},
                    "student_id": {"type": "integer", "default": 0},
                },
            },
            handler=_t_get_exercise_records,
            category="query",
            agent="both",
        ),
        Tool(
            name="search_student",
            description="按姓名或学号模糊搜索当前课程内的学生。适合'学号 20241 开头的有哪些'。",
            parameters={
                "type": "object",
                "properties": {"keyword": {"type": "string"}},
                "required": ["keyword"],
            },
            handler=_t_search_student,
            category="query",
            agent="both",
        ),
    ]
    for t in tools:
        registry.register(t)
