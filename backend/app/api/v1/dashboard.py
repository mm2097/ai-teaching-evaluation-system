"""看板 API：统计数据、学生首页、成绩趋势。"""
from collections import defaultdict
from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    Student, Course, Teacher, ScoreRecord, AttendanceRecord,
    StudyWarning, CourseStudent, ExamBatch, SysUser, SysRole,
    IndividualScore, CourseTestDetail, AttendanceSheet, ClassInfo,
    AnswerTask, AnswerTaskClass, StudentAnswerRecord, KnowledgeMastery,
)
from app.models.question import TASK_TYPE_SELF_PRACTICE

router = APIRouter()


def _average(values: list[float]) -> float | None:
    """Return a one-decimal average while preserving the no-data state."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _rank_text(value: float | None, peer_values: list[float]) -> tuple[int | None, str]:
    """Convert a score into a class percentile label."""
    if value is None or not peer_values:
        return None, "暂无"
    rank = 1 + sum(1 for peer_value in peer_values if peer_value > value)
    percentile = max(1, ceil(rank / len(peer_values) * 100))
    return rank, f"前{percentile}%"


# ============================================================================
# 权限校验辅助
# ============================================================================

def _check_dashboard_access(
    session: Session,
    current_user: SysUser,
    course_id: int | None,
) -> None:
    """校验看板数据查看权限。

    - 任课教师（teacher）：查看本课程时必须是自己授课的课程；不指定课程时允许
    - 学生（student）：无权查看看板统计
    - 管理员（admin）：使用系统治理工作台，不接触教学统计
    """
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


@router.get("/dashboard/stats", tags=["看板"])
def get_stats(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """首页统计数据。

    权限：仅任课教师可查看。支持按班级筛选。
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

    # 成绩统计（按学生维度：每人取平均分，再统计及格/优秀人数）
    from collections import defaultdict

    stu_score_list: dict[int, list[float]] = defaultdict(list)

    def _add_score(student_id_val: int, score_val: float) -> None:
        if not cls_ids or student_id_val in cls_ids:
            stu_score_list[student_id_val].append(score_val)

    score_q = select(ScoreRecord)
    if course_id:
        score_q = score_q.where(ScoreRecord.course_id == course_id)
    for s in session.exec(score_q).all():
        _add_score(s.student_id, s.score)

    if course_id:
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            for s in session.exec(select(IndividualScore).where(IndividualScore.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                _add_score(s.student_id, s.score)
            for s in session.exec(select(CourseTestDetail).where(CourseTestDetail.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                _add_score(s.student_id, s.total_score)
    else:
        for s in session.exec(select(IndividualScore)).all():
            _add_score(s.student_id, s.score)
        for s in session.exec(select(CourseTestDetail)).all():
            _add_score(s.student_id, s.total_score)

    stu_avgs = [sum(scores) / len(scores) for scores in stu_score_list.values()]
    total_stu = len(stu_avgs) or 1
    pass_count = sum(1 for a in stu_avgs if a >= 60)
    excellent = sum(1 for a in stu_avgs if a >= 90)
    pass_rate = round(pass_count / total_stu * 100, 1)
    excellent_rate = round(excellent / total_stu * 100, 1)

    # 考勤率（按学生维度：每人算出勤率，再取平均）
    stu_att_normal: dict[int, int] = defaultdict(int)
    stu_att_total: dict[int, int] = defaultdict(int)

    att_q = select(AttendanceRecord)
    if course_id:
        att_q = att_q.where(AttendanceRecord.course_id == course_id)
    for a in session.exec(att_q).all():
        sid = getattr(a, 'student_id', None)
        if sid and (not cls_ids or sid in cls_ids):
            stu_att_total[sid] += 1
            if a.status == 0:
                stu_att_normal[sid] += 1

    if course_id:
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            for a in session.exec(select(AttendanceSheet).where(AttendanceSheet.exam_batch_id.in_(batch_ids))).all():  # type: ignore[arg-type]
                sid = getattr(a, 'student_id', None)
                if sid and (not cls_ids or sid in cls_ids):
                    if a.total_count and a.present_count:
                        stu_att_total[sid] += a.total_count
                        stu_att_normal[sid] += a.present_count
    else:
        for a in session.exec(select(AttendanceSheet)).all():
            sid = getattr(a, 'student_id', None)
            if sid and (not cls_ids or sid in cls_ids):
                if a.total_count and a.present_count:
                    stu_att_total[sid] += a.total_count
                    stu_att_normal[sid] += a.present_count

    att_rates = [
        stu_att_normal[sid] / (stu_att_total[sid] or 1)
        for sid in set(list(stu_att_normal.keys()) + list(stu_att_total.keys()))
    ]
    attendance_rate = round(sum(att_rates) / (len(att_rates) or 1) * 100, 1)

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


@router.get("/dashboard/student-overview", tags=["看板"])
def get_student_overview(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Aggregate the current student's dashboard from persisted teaching data."""
    role = session.get(SysRole, current_user.role_id)
    if not role or role.role_code != "student":
        raise HTTPException(status_code=403, detail="仅学生可查看个人首页")

    student = session.exec(
        select(Student).where(Student.user_id == current_user.user_id)
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="当前账号未关联学生信息")

    enrollments = session.exec(
        select(CourseStudent).where(
            CourseStudent.student_id == student.student_id,
            CourseStudent.status == 1,
        )
    ).all()
    course_ids = sorted({item.course_id for item in enrollments})
    courses = []
    if course_ids:
        courses = session.exec(
            select(Course).where(Course.course_id.in_(course_ids))  # type: ignore[arg-type]
        ).all()
        courses.sort(key=lambda item: item.course_name)

    class_info = session.get(ClassInfo, student.class_id)
    if not course_ids:
        return {
            "student": {
                "id": student.student_id,
                "studentNo": student.student_no,
                "name": student.real_name,
                "classId": student.class_id,
                "className": class_info.class_name if class_info else "",
                "college": class_info.college if class_info else "",
            },
            "summary": {
                "courseCount": 0,
                "averageScore": None,
                "attendanceRate": None,
                "pendingQuizCount": 0,
                "weakKnowledgeCount": 0,
                "classRank": None,
                "classRankText": "暂无",
                "classStudentCount": 0,
            },
            "courses": [],
        }

    # Build course -> student -> scores from all three supported score tables.
    course_scores: dict[int, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    all_enrollments = session.exec(
        select(CourseStudent).where(
            CourseStudent.course_id.in_(course_ids),  # type: ignore[arg-type]
            CourseStudent.status == 1,
        )
    ).all()
    enrolled_ids_by_course: dict[int, set[int]] = defaultdict(set)
    all_enrolled_student_ids: set[int] = set()
    for enrollment in all_enrollments:
        enrolled_ids_by_course[enrollment.course_id].add(enrollment.student_id)
        all_enrolled_student_ids.add(enrollment.student_id)

    legacy_scores = session.exec(
        select(ScoreRecord).where(
            ScoreRecord.course_id.in_(course_ids),  # type: ignore[arg-type]
            ScoreRecord.student_id.in_(all_enrolled_student_ids),  # type: ignore[arg-type]
        )
    ).all()
    for score in legacy_scores:
        course_scores[score.course_id][score.student_id].append(score.score)

    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all()
    batch_course = {
        batch.batch_id: batch.course_id
        for batch in batches
        if batch.batch_id is not None
    }
    batch_ids = list(batch_course)
    if batch_ids:
        individual_scores = session.exec(
            select(IndividualScore).where(
                IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                IndividualScore.student_id.in_(all_enrolled_student_ids),  # type: ignore[arg-type]
            )
        ).all()
        for score in individual_scores:
            course_id = batch_course.get(score.exam_batch_id)
            if course_id is not None:
                course_scores[course_id][score.student_id].append(score.score)

        test_scores = session.exec(
            select(CourseTestDetail).where(
                CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                CourseTestDetail.student_id.in_(all_enrolled_student_ids),  # type: ignore[arg-type]
            )
        ).all()
        for score in test_scores:
            course_id = batch_course.get(score.exam_batch_id)
            if course_id is not None:
                course_scores[course_id][score.student_id].append(score.total_score)

    students_by_id: dict[int, Student] = {}
    if all_enrolled_student_ids:
        enrolled_students = session.exec(
            select(Student).where(
                Student.student_id.in_(all_enrolled_student_ids)  # type: ignore[arg-type]
            )
        ).all()
        students_by_id = {
            item.student_id: item
            for item in enrolled_students
            if item.student_id is not None
        }

    teachers_by_id: dict[int, Teacher] = {}
    teacher_ids = {course.teacher_id for course in courses}
    if teacher_ids:
        teachers = session.exec(
            select(Teacher).where(Teacher.teacher_id.in_(teacher_ids))  # type: ignore[arg-type]
        ).all()
        teachers_by_id = {
            item.teacher_id: item
            for item in teachers
            if item.teacher_id is not None
        }

    # Assignment completion is the only persisted progress signal in this project.
    tasks = session.exec(
        select(AnswerTask).where(AnswerTask.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all()
    tasks = [
        task for task in tasks
        if task.status in (1, 2) and task.task_type != TASK_TYPE_SELF_PRACTICE
    ]
    task_ids = [task.task_id for task in tasks if task.task_id is not None]
    task_targets: dict[int, int] = {}
    submitted_task_ids: set[int] = set()
    if task_ids:
        task_targets = {
            item.task_id: item.class_id
            for item in session.exec(
                select(AnswerTaskClass).where(
                    AnswerTaskClass.task_id.in_(task_ids)  # type: ignore[arg-type]
                )
            ).all()
        }
        submitted_task_ids = set(session.exec(
            select(StudentAnswerRecord.task_id).where(
                StudentAnswerRecord.student_id == student.student_id,
                StudentAnswerRecord.task_id.in_(task_ids),  # type: ignore[arg-type]
            ).distinct()
        ).all())

    eligible_tasks = [
        task for task in tasks
        if task.task_id not in task_targets
        or task_targets[task.task_id] == student.class_id
    ]
    now = datetime.now()
    pending_quiz_count = 0
    for task in eligible_tasks:
        deadline = task.deadline.replace(tzinfo=None) if task.deadline.tzinfo else task.deadline
        if task.status == 1 and deadline >= now and task.task_id not in submitted_task_ids:
            pending_quiz_count += 1

    tasks_by_course: dict[int, list[AnswerTask]] = defaultdict(list)
    for task in eligible_tasks:
        tasks_by_course[task.course_id].append(task)

    # Aggregate the current student's attendance over their enrolled courses.
    attendance_total = 0
    attendance_present = 0
    attendance_records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id.in_(course_ids),  # type: ignore[arg-type]
            AttendanceRecord.student_id == student.student_id,
        )
    ).all()
    attendance_total += len(attendance_records)
    attendance_present += sum(1 for item in attendance_records if item.status == 0)

    if batch_ids:
        attendance_sheets = session.exec(
            select(AttendanceSheet).where(
                AttendanceSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                AttendanceSheet.student_id == student.student_id,
            )
        ).all()
        for sheet in attendance_sheets:
            if sheet.total_count is not None and sheet.total_count > 0:
                attendance_total += sheet.total_count
                attendance_present += sheet.present_count or 0
    attendance_rate = (
        round(attendance_present / attendance_total * 100, 1)
        if attendance_total else None
    )

    weak_knowledge = session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.course_id.in_(course_ids),  # type: ignore[arg-type]
            KnowledgeMastery.student_id == student.student_id,
            KnowledgeMastery.mastery_score < 75,
        )
    ).all()
    weak_knowledge_count = len({(item.course_id, item.point_id) for item in weak_knowledge})

    course_items: list[dict] = []
    student_course_averages: list[float] = []
    for course in courses:
        student_score = _average(
            course_scores[course.course_id].get(student.student_id, [])
        )
        if student_score is not None:
            student_course_averages.append(student_score)

        peer_scores = []
        for peer_id in enrolled_ids_by_course[course.course_id]:
            peer = students_by_id.get(peer_id)
            if not peer or peer.class_id != student.class_id:
                continue
            peer_score = _average(course_scores[course.course_id].get(peer_id, []))
            if peer_score is not None:
                peer_scores.append(peer_score)
        course_rank, course_rank_text = _rank_text(student_score, peer_scores)

        course_tasks = tasks_by_course.get(course.course_id, [])
        progress = None
        if course_tasks:
            completed_count = sum(
                1 for task in course_tasks if task.task_id in submitted_task_ids
            )
            progress = round(completed_count / len(course_tasks) * 100)

        teacher = teachers_by_id.get(course.teacher_id)
        course_items.append({
            "id": course.course_id,
            "name": course.course_name,
            "teacher": teacher.real_name if teacher else "暂无",
            "score": student_score,
            "avgScore": _average(peer_scores),
            "rank": course_rank,
            "rankText": course_rank_text,
            "progress": progress,
        })

    average_score = _average(student_course_averages)
    class_peer_averages: list[float] = []
    class_student_ids = {
        item.student_id
        for item in students_by_id.values()
        if item.class_id == student.class_id and item.student_id is not None
    }
    for peer_id in class_student_ids:
        peer_course_averages = [
            score
            for course_id in course_ids
            if (score := _average(course_scores[course_id].get(peer_id, []))) is not None
        ]
        peer_average = _average(peer_course_averages)
        if peer_average is not None:
            class_peer_averages.append(peer_average)
    class_rank, class_rank_text = _rank_text(average_score, class_peer_averages)

    return {
        "student": {
            "id": student.student_id,
            "studentNo": student.student_no,
            "name": student.real_name,
            "classId": student.class_id,
            "className": class_info.class_name if class_info else "",
            "college": class_info.college if class_info else "",
        },
        "summary": {
            "courseCount": len(course_items),
            "averageScore": average_score,
            "attendanceRate": attendance_rate,
            "pendingQuizCount": pending_quiz_count,
            "weakKnowledgeCount": weak_knowledge_count,
            "classRank": class_rank,
            "classRankText": class_rank_text,
            "classStudentCount": len(class_peer_averages),
        },
        "courses": course_items,
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
    - 教师可查看班级或课程级趋势
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
        # 教师：校验课程权限；管理员会被拒绝
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
