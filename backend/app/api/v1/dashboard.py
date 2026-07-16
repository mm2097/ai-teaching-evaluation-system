"""看板 API：统计数据、成绩趋势。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    Student, Course, Teacher, ScoreRecord, AttendanceRecord,
    StudyWarning, CourseStudent, ExamBatch, SysUser, SysRole,
    IndividualScore, CourseTestDetail, AttendanceSheet, ClassInfo,
)

router = APIRouter()


# ============================================================================
# 权限校验辅助
# ============================================================================

def _check_dashboard_access(
    session: Session,
    current_user: SysUser,
    course_id: int | None,
) -> None:
    """校验看板数据查看权限。

    - 管理员（admin）：可查看全部
    - 任课教师（teacher）：查看本课程时必须是自己授课的课程；不指定课程时允许
    - 学生（student）：无权查看看板统计
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "admin":
        return

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


@router.get("/dashboard/stats", tags=["看板"])
def get_stats(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """首页统计数据。

    权限：仅管理员和任课教师可查看。支持按班级筛选。
    """
    _check_dashboard_access(session, current_user, course_id)

    # 获取班级内学生 ID 集合
    def _class_stu_ids() -> set[int]:
        if not class_id:
            return set()
        return set(session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all())

    cls_ids = _class_stu_ids()

    # 学生数
    stu_q = select(CourseStudent.student_id).distinct()
    if course_id:
        stu_q = stu_q.where(CourseStudent.course_id == course_id)
    all_stu = list(session.exec(stu_q).all())
    if cls_ids:
        all_stu = [s for s in all_stu if s in cls_ids]
    student_count = len(all_stu)

    # 课程数（班级不改变课程维度）
    crs_q = select(Course)
    if course_id:
        crs_q = crs_q.where(Course.course_id == course_id)
    course_count = len(session.exec(crs_q).all())

    teacher_count = len(session.exec(select(Teacher)).all())

    # 成绩统计
    all_scores: list[float] = []
    score_q = select(ScoreRecord)
    if course_id:
        score_q = score_q.where(ScoreRecord.course_id == course_id)
    for s in session.exec(score_q).all():
        if not cls_ids or getattr(s, 'student_id', None) in cls_ids:
            all_scores.append(s.score)

    if course_id:
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            for s in session.exec(select(IndividualScore).where(IndividualScore.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                if not cls_ids or getattr(s, 'student_id', None) in cls_ids:
                    all_scores.append(s.score)
            for s in session.exec(select(CourseTestDetail).where(CourseTestDetail.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                if not cls_ids or getattr(s, 'student_id', None) in cls_ids:
                    all_scores.append(s.total_score)
    else:
        for s in session.exec(select(IndividualScore)).all():
            if not cls_ids or getattr(s, 'student_id', None) in cls_ids:
                all_scores.append(s.score)
        for s in session.exec(select(CourseTestDetail)).all():
            if not cls_ids or getattr(s, 'student_id', None) in cls_ids:
                all_scores.append(s.total_score)

    total = len(all_scores) or 1
    pass_count = sum(1 for s in all_scores if s >= 60)
    excellent = sum(1 for s in all_scores if s >= 90)
    pass_rate = round(pass_count / total * 100, 1)
    excellent_rate = round(excellent / total * 100, 1)

    # 考勤率
    att_normal = 0
    att_total = 0
    att_q = select(AttendanceRecord)
    if course_id:
        att_q = att_q.where(AttendanceRecord.course_id == course_id)
    for a in session.exec(att_q).all():
        if not cls_ids or getattr(a, 'student_id', None) in cls_ids:
            att_total += 1
            if a.status == 0:
                att_normal += 1
    if course_id:
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            for a in session.exec(select(AttendanceSheet).where(AttendanceSheet.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                if not cls_ids or getattr(a, 'student_id', None) in cls_ids:
                    if a.total_count and a.present_count:
                        att_total += a.total_count
                        att_normal += a.present_count
    else:
        for a in session.exec(select(AttendanceSheet)).all():
            if not cls_ids or getattr(a, 'student_id', None) in cls_ids:
                if a.total_count and a.present_count:
                    att_total += a.total_count
                    att_normal += a.present_count
    attendance_rate = round(att_normal / (att_total or 1) * 100, 1)

    # 预警数
    warn_q = select(StudyWarning)
    if course_id:
        warn_q = warn_q.where(StudyWarning.course_id == course_id)
    all_warns = list(session.exec(warn_q).all())
    if cls_ids:
        all_warns = [w for w in all_warns if getattr(w, 'student_id', None) in cls_ids]
    warning_count = len(all_warns)

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
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """按批次计算成绩趋势（用于折线图）。支持班级或个人维度。

    权限：
    - 教师/管理员可查看班级或课程级趋势
    - 学生仅可查看自己的成绩趋势（student_id 须与本人一致）
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "student":
        # 学生仅可查看自己的趋势
        if not student_id:
            raise HTTPException(status_code=403, detail="学生只能查看自己的成绩趋势，请指定 student_id")
        student = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not student or student.student_id != student_id:
            raise HTTPException(status_code=403, detail="学生仅可查看自己的成绩趋势")
    else:
        # 教师/管理员：校验课程权限
        _check_dashboard_access(session, current_user, course_id)
    stmt = select(ExamBatch)
    if course_id:
        stmt = stmt.where(ExamBatch.course_id == course_id)
    batches = session.exec(stmt).all()
    batches.sort(key=lambda b: b.create_time)

    months: list[str] = []
    avg_scores: list[int] = []
    pass_rates: list[int] = []
    max_scores: list[int] = []
    min_scores: list[int] = []

    for batch in batches:
        # 合并新旧表成绩
        sc: list[float] = []

        # 旧表 ScoreRecord
        sq = select(ScoreRecord.score).where(ScoreRecord.batch_id == batch.batch_id)
        if student_id:
            sq = sq.where(ScoreRecord.student_id == student_id)
        sr_scores = session.exec(sq).all()
        if class_id and not student_id:
            class_stu_ids = set(session.exec(
                select(Student.student_id).where(Student.class_id == class_id)
            ).all())
            sr_scores = [s for s in sr_scores if s in class_stu_ids]  # This is wrong - need to query differently
            # Re-query properly
            all_sr = session.exec(
                select(ScoreRecord).where(ScoreRecord.batch_id == batch.batch_id)
            ).all()
            sc.extend([r.score for r in all_sr if r.student_id in class_stu_ids])
        else:
            sc.extend(sr_scores)

        # IndividualScore
        is_scores = session.exec(
            select(IndividualScore).where(IndividualScore.exam_batch_id == batch.batch_id)
        ).all()
        if student_id:
            sc.extend([s.score for s in is_scores if s.student_id == student_id])
        elif class_id:
            if 'class_stu_ids' not in dir():
                class_stu_ids = set(session.exec(
                    select(Student.student_id).where(Student.class_id == class_id)
                ).all())
            sc.extend([s.score for s in is_scores if s.student_id in class_stu_ids])
        else:
            sc.extend([s.score for s in is_scores])

        # CourseTestDetail
        ct_scores = session.exec(
            select(CourseTestDetail).where(CourseTestDetail.exam_batch_id == batch.batch_id)
        ).all()
        if student_id:
            sc.extend([s.total_score for s in ct_scores if s.student_id == student_id])
        elif class_id:
            if 'class_stu_ids' not in dir():
                class_stu_ids = set(session.exec(
                    select(Student.student_id).where(Student.class_id == class_id)
                ).all())
            sc.extend([s.total_score for s in ct_scores if s.student_id in class_stu_ids])
        else:
            sc.extend([s.total_score for s in ct_scores])

        if not sc:
            continue

        months.append(batch.batch_name)
        avg_scores.append(round(sum(sc) / len(sc)))
        pass_rates.append(round(sum(1 for s in sc if s >= 60) / len(sc) * 100))
        max_scores.append(int(max(sc)))
        min_scores.append(int(min(sc)))

    return {
        "months": months,
        "labels": months,         # 兼容前端旧字段名
        "avgScore": avg_scores,
        "passRate": pass_rates,
        "maxScore": max_scores,
        "minScore": min_scores,
    }
