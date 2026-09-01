"""看板 API：统计数据、成绩趋势。"""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    AnswerTask,
    AnswerTaskClass,
    AttendanceRecord,
    AttendanceSheet,
    ClassInfo,
    Course,
    CourseStudent,
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    ScoreRecord,
    Student,
    StudentAnswerRecord,
    StudyWarning,
    SysRole,
    SysUser,
    Teacher,
)

router = APIRouter()


def _check_dashboard_access(
    session: Session,
    current_user: SysUser,
    course_id: int | None,
) -> None:
    """校验看板数据查看权限。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "teacher":
        if course_id is not None:
            course = session.get(Course, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="课程不存在")
            teacher = session.exec(
                select(Teacher).where(Teacher.user_id == current_user.user_id)
            ).first()
            if not teacher:
                raise HTTPException(status_code=403, detail="当前账号未关联教师信息")
            if course.teacher_id != teacher.teacher_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"仅授课教师可查看课程「{course.course_name}」的统计数据",
                )
        return

    raise HTTPException(status_code=403, detail="无权查看看板数据")


def _class_student_ids(session: Session, class_id: int | None) -> set[int]:
    if not class_id:
        return set()
    return set(session.exec(
        select(Student.student_id).where(Student.class_id == class_id)
    ).all())


def _course_batch_ids(session: Session, course_id: int | None) -> list[int]:
    if not course_id:
        return []
    return list(session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all())


def _add_score_if_allowed(
    bucket: dict[int, list[float]],
    student_id: int,
    score: float,
    class_ids: set[int],
) -> None:
    if not class_ids or student_id in class_ids:
        bucket[student_id].append(float(score))


def _task_target_students(
    session: Session,
    task: AnswerTask,
    class_id: int | None,
    enrolled_students: set[int],
) -> set[int]:
    class_link = session.exec(
        select(AnswerTaskClass).where(AnswerTaskClass.task_id == task.task_id)
    ).first()
    target_class_id = class_link.class_id if class_link else class_id
    if target_class_id:
        class_students = _class_student_ids(session, target_class_id)
        return enrolled_students & class_students
    return set(enrolled_students)


def _ai_completion_rate(
    session: Session,
    course_id: int | None,
    class_id: int | None,
    enrolled_students: list[int],
) -> float:
    """AI 辅助教学完成率：教师发布练习的学生提交覆盖率。"""
    if not course_id:
        return 0.0
    enrolled_set = set(enrolled_students)
    if not enrolled_set:
        return 0.0

    tasks = session.exec(
        select(AnswerTask).where(
            AnswerTask.course_id == course_id,
            AnswerTask.task_type == "assignment",
            AnswerTask.status.in_([1, 2]),
        )
    ).all()
    if not tasks:
        return 0.0

    expected = 0
    completed = 0
    for task in tasks:
        target_students = _task_target_students(session, task, class_id, enrolled_set)
        if not target_students:
            continue
        expected += len(target_students)
        submitted = set(session.exec(
            select(StudentAnswerRecord.student_id)
            .where(StudentAnswerRecord.task_id == task.task_id)
            .distinct()
        ).all())
        completed += len(target_students & submitted)

    if expected <= 0:
        return 0.0
    return round(completed / expected * 100, 1)


@router.get("/dashboard/stats", tags=["看板"])
def get_stats(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """首页统计数据。权限：仅任课教师可查看。支持按班级筛选。"""
    _check_dashboard_access(session, current_user, course_id)

    cls_ids = _class_student_ids(session, class_id)

    stu_q = select(CourseStudent.student_id).distinct()
    if course_id:
        stu_q = stu_q.where(CourseStudent.course_id == course_id)
    all_stu = list(session.exec(stu_q).all())
    if cls_ids:
        all_stu = [s for s in all_stu if s in cls_ids]
    student_count = len(all_stu)

    crs_q = select(Course)
    if course_id:
        crs_q = crs_q.where(Course.course_id == course_id)
    course_count = len(session.exec(crs_q).all())
    teacher_count = len(session.exec(select(Teacher)).all())

    stu_score_list: dict[int, list[float]] = defaultdict(list)

    score_q = select(ScoreRecord)
    if course_id:
        score_q = score_q.where(ScoreRecord.course_id == course_id)
    for score in session.exec(score_q).all():
        _add_score_if_allowed(stu_score_list, score.student_id, score.score, cls_ids)

    batch_ids = _course_batch_ids(session, course_id)
    if course_id:
        if batch_ids:
            for score in session.exec(
                select(IndividualScore).where(IndividualScore.exam_batch_id.in_(batch_ids))  # type: ignore[arg-type]
            ).all():
                _add_score_if_allowed(stu_score_list, score.student_id, score.score, cls_ids)
            for score in session.exec(
                select(CourseTestDetail).where(CourseTestDetail.exam_batch_id.in_(batch_ids))  # type: ignore[arg-type]
            ).all():
                _add_score_if_allowed(stu_score_list, score.student_id, score.total_score, cls_ids)
    else:
        for score in session.exec(select(IndividualScore)).all():
            _add_score_if_allowed(stu_score_list, score.student_id, score.score, cls_ids)
        for score in session.exec(select(CourseTestDetail)).all():
            _add_score_if_allowed(stu_score_list, score.student_id, score.total_score, cls_ids)

    stu_avgs = [sum(scores) / len(scores) for scores in stu_score_list.values()]
    total_stu = len(stu_avgs) or 1
    pass_count = sum(1 for avg in stu_avgs if avg >= 60)
    excellent = sum(1 for avg in stu_avgs if avg >= 90)
    pass_rate = round(pass_count / total_stu * 100, 1)
    excellent_rate = round(excellent / total_stu * 100, 1)

    stu_att_normal: dict[int, int] = defaultdict(int)
    stu_att_total: dict[int, int] = defaultdict(int)

    att_q = select(AttendanceRecord)
    if course_id:
        att_q = att_q.where(AttendanceRecord.course_id == course_id)
    for attendance in session.exec(att_q).all():
        sid = getattr(attendance, "student_id", None)
        if sid and (not cls_ids or sid in cls_ids):
            stu_att_total[sid] += 1
            if attendance.status == 0:
                stu_att_normal[sid] += 1

    if course_id:
        if batch_ids:
            for attendance in session.exec(
                select(AttendanceSheet).where(AttendanceSheet.exam_batch_id.in_(batch_ids))  # type: ignore[arg-type]
            ).all():
                sid = getattr(attendance, "student_id", None)
                if sid and (not cls_ids or sid in cls_ids):
                    if attendance.total_count and attendance.present_count is not None:
                        stu_att_total[sid] += attendance.total_count
                        stu_att_normal[sid] += attendance.present_count
    else:
        for attendance in session.exec(select(AttendanceSheet)).all():
            sid = getattr(attendance, "student_id", None)
            if sid and (not cls_ids or sid in cls_ids):
                if attendance.total_count and attendance.present_count is not None:
                    stu_att_total[sid] += attendance.total_count
                    stu_att_normal[sid] += attendance.present_count

    att_rates = [
        stu_att_normal[sid] / (stu_att_total[sid] or 1)
        for sid in set(list(stu_att_normal.keys()) + list(stu_att_total.keys()))
    ]
    attendance_rate = round(sum(att_rates) / (len(att_rates) or 1) * 100, 1)

    warn_q = select(StudyWarning)
    if course_id:
        warn_q = warn_q.where(StudyWarning.course_id == course_id)
    all_warns = list(session.exec(warn_q).all())
    if cls_ids:
        all_warns = [w for w in all_warns if getattr(w, "student_id", None) in cls_ids]
    warning_count = len(all_warns)
    ai_completion_rate = _ai_completion_rate(session, course_id, class_id, all_stu)

    return {
        "studentCount": student_count,
        "courseCount": course_count,
        "teacherCount": teacher_count,
        "passRate": pass_rate,
        "excellentRate": excellent_rate,
        "attendanceRate": attendance_rate,
        "warningCount": warning_count,
        "aiCompletionRate": ai_completion_rate,
    }


@router.get("/dashboard/grade-trend", tags=["看板"])
def get_grade_trend(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """按批次计算成绩趋势（用于折线图）。支持班级或个人维度。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "student":
        if not student_id:
            raise HTTPException(status_code=403, detail="学生只能查看自己的成绩趋势，请指定 student_id")
        student = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not student or student.student_id != student_id:
            raise HTTPException(status_code=403, detail="学生仅可查看自己的成绩趋势")
    else:
        _check_dashboard_access(session, current_user, course_id)

    stmt = select(ExamBatch)
    if course_id:
        stmt = stmt.where(ExamBatch.course_id == course_id)
    batches = session.exec(stmt).all()
    batches.sort(key=lambda batch: batch.create_time)

    class_stu_ids = _class_student_ids(session, class_id) if class_id and not student_id else set()
    months: list[str] = []
    avg_scores: list[int] = []
    pass_rates: list[int] = []
    excellent_rates: list[int] = []
    max_scores: list[int] = []
    min_scores: list[int] = []

    for batch in batches:
        scores: list[float] = []

        score_records = session.exec(
            select(ScoreRecord).where(ScoreRecord.batch_id == batch.batch_id)
        ).all()
        for row in score_records:
            if student_id and row.student_id != student_id:
                continue
            if class_stu_ids and row.student_id not in class_stu_ids:
                continue
            scores.append(float(row.score))

        individual_scores = session.exec(
            select(IndividualScore).where(IndividualScore.exam_batch_id == batch.batch_id)
        ).all()
        for row in individual_scores:
            if student_id and row.student_id != student_id:
                continue
            if class_stu_ids and row.student_id not in class_stu_ids:
                continue
            scores.append(float(row.score))

        detail_scores = session.exec(
            select(CourseTestDetail).where(CourseTestDetail.exam_batch_id == batch.batch_id)
        ).all()
        for row in detail_scores:
            if student_id and row.student_id != student_id:
                continue
            if class_stu_ids and row.student_id not in class_stu_ids:
                continue
            scores.append(float(row.total_score))

        if not scores:
            continue

        months.append(batch.batch_name)
        avg_scores.append(round(sum(scores) / len(scores)))
        pass_rates.append(round(sum(1 for score in scores if score >= 60) / len(scores) * 100))
        excellent_rates.append(round(sum(1 for score in scores if score >= 90) / len(scores) * 100))
        max_scores.append(int(max(scores)))
        min_scores.append(int(min(scores)))

    return {
        "months": months,
        "labels": months,
        "avgScore": avg_scores,
        "passRate": pass_rates,
        "excellentRate": excellent_rates,
        "maxScore": max_scores,
        "minScore": min_scores,
    }