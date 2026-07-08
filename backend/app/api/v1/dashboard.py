"""看板 API：统计数据、成绩趋势。"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.models import (
    Student, Course, Teacher, ScoreRecord, AttendanceRecord,
    StudyWarning, CourseStudent, ExamBatch, SysUser,
)

router = APIRouter()


@router.get("/dashboard/stats", tags=["看板"])
def get_stats(
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """首页统计数据。"""
    # 学生数：有选课关系的去重学生
    stu_q = select(CourseStudent.student_id).distinct()
    if course_id:
        stu_q = stu_q.where(CourseStudent.course_id == course_id)
    student_count = len(session.exec(stu_q).all())

    # 课程数
    crs_q = select(Course)
    if course_id:
        crs_q = crs_q.where(Course.course_id == course_id)
    course_count = len(session.exec(crs_q).all())

    teacher_count = len(session.exec(select(Teacher)).all())

    # 成绩统计
    score_q = select(ScoreRecord)
    if course_id:
        score_q = score_q.where(ScoreRecord.course_id == course_id)
    scores = session.exec(score_q).all()
    total = len(scores) or 1
    pass_count = sum(1 for s in scores if s.is_pass == 1)
    excellent = sum(1 for s in scores if s.score >= 90)
    pass_rate = round(pass_count / total * 100, 1)
    excellent_rate = round(excellent / total * 100, 1)

    # 考勤率
    att_q = select(AttendanceRecord)
    if course_id:
        att_q = att_q.where(AttendanceRecord.course_id == course_id)
    atts = session.exec(att_q).all()
    att_total = len(atts) or 1
    att_normal = sum(1 for a in atts if a.status == 0)
    attendance_rate = round(att_normal / att_total * 100, 1)

    # 预警数
    warn_q = select(StudyWarning)
    if course_id:
        warn_q = warn_q.where(StudyWarning.course_id == course_id)
    warning_count = len(session.exec(warn_q).all())

    return {
        "studentCount": student_count,
        "courseCount": course_count,
        "teacherCount": teacher_count,
        "passRate": pass_rate,
        "excellentRate": excellent_rate,
        "attendanceRate": attendance_rate,
        "warningCount": warning_count,
    }


@router.get("/dashboard/grade-trend", tags=["看板"])
def get_grade_trend(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """按批次计算成绩趋势（用于折线图）。支持班级或个人维度。"""
    stmt = select(ExamBatch)
    if course_id:
        stmt = stmt.where(ExamBatch.course_id == course_id)
    batches = session.exec(stmt).all()
    batches.sort(key=lambda b: b.exam_time or b.create_time)

    months: list[str] = []
    avg_scores: list[int] = []
    pass_rates: list[int] = []
    max_scores: list[int] = []
    min_scores: list[int] = []

    for batch in batches:
        sq = select(ScoreRecord).where(ScoreRecord.batch_id == batch.batch_id)

        # 个人维度：只查该学生的成绩
        if student_id:
            sq = sq.where(ScoreRecord.student_id == student_id)
            records = session.exec(sq).all()
        elif class_id:
            # 班级维度：先拿到班级学生，再过滤
            class_stu_ids = set(session.exec(
                select(Student.student_id).where(Student.class_id == class_id)
            ).all())
            all_records = session.exec(sq).all()
            records = [r for r in all_records if r.student_id in class_stu_ids]
        else:
            records = session.exec(sq).all()

        if not records:
            continue

        sc = [r.score for r in records]
        months.append(batch.batch_name)
        avg_scores.append(round(sum(sc) / len(sc)))
        pass_rates.append(round(sum(1 for r in records if r.is_pass) / len(records) * 100))
        max_scores.append(int(max(sc)))
        min_scores.append(int(min(sc)))

    return {
        "months": months,
        "avgScore": avg_scores,
        "passRate": pass_rates,
        "maxScore": max_scores,
        "minScore": min_scores,
    }
