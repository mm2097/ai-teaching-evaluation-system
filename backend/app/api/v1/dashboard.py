"""看板 API：统计数据、学生首页、成绩趋势。"""
from collections import defaultdict
from datetime import datetime
from math import ceil

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
    KnowledgeMastery,
    ScoreRecord,
    Student,
    StudentAnswerRecord,
    StudyWarning,
    SysRole,
    SysUser,
    Teacher,
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


@router.get("/dashboard/student-score-archive", tags=["看板"])
def get_student_score_archive(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """学生个人成绩档案：历次考试成绩明细（含班级均分与排名）。

    权限：仅学生本人可查看，数据按当前登录学生隔离。
    """
    role = session.get(SysRole, current_user.role_id)
    if not role or role.role_code != "student":
        raise HTTPException(status_code=403, detail="仅学生可查看个人成绩档案")

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
    if not course_ids:
        return {"records": []}

    courses = session.exec(
        select(Course).where(Course.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all()
    course_map = {item.course_id: item for item in courses}

    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all()
    batches.sort(key=lambda b: (b.course_id, b.create_time))
    batch_ids = [b.batch_id for b in batches if b.batch_id is not None]

    # 同班同学（用于计算班级均分与排名）
    class_student_ids = set(session.exec(
        select(Student.student_id).where(Student.class_id == student.class_id)
    ).all())

    # 收集成绩：batch_id -> {student_id: [scores]}（合并新旧三张成绩表）
    batch_scores: dict[int, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    def _add(batch_id_val: int | None, student_id_val: int, score_val: float | None) -> None:
        if batch_id_val is None or score_val is None:
            return
        batch_scores[batch_id_val][student_id_val].append(float(score_val))

    for r in session.exec(
        select(ScoreRecord).where(
            ScoreRecord.course_id.in_(course_ids),  # type: ignore[arg-type]
            ScoreRecord.student_id.in_(class_student_ids),  # type: ignore[arg-type]
        )
    ).all():
        _add(r.batch_id, r.student_id, r.score)

    if batch_ids:
        for r in session.exec(
            select(IndividualScore).where(
                IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                IndividualScore.student_id.in_(class_student_ids),  # type: ignore[arg-type]
            )
        ).all():
            _add(r.exam_batch_id, r.student_id, r.score)

        for r in session.exec(
            select(CourseTestDetail).where(
                CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                CourseTestDetail.student_id.in_(class_student_ids),  # type: ignore[arg-type]
            )
        ).all():
            _add(r.exam_batch_id, r.student_id, r.total_score)

    records: list[dict] = []
    for batch in batches:
        if batch.batch_id is None:
            continue
        my_scores = batch_scores[batch.batch_id].get(student.student_id, [])
        if not my_scores:
            continue  # 该批次下本人无成绩（如考勤批次），跳过
        my_score = round(sum(my_scores) / len(my_scores), 1)

        peer_values: list[float] = []
        for sid in class_student_ids:
            vals = batch_scores[batch.batch_id].get(sid)
            if vals:
                peer_values.append(sum(vals) / len(vals))
        class_avg = round(sum(peer_values) / len(peer_values), 1)
        rank = 1 + sum(1 for v in peer_values if v > my_score)

        course = course_map.get(batch.course_id)
        records.append({
            "id": batch.batch_id,
            "courseName": course.course_name if course else "",
            "semester": batch.semester,
            "type": batch.batch_name,
            "score": my_score,
            "total": batch.full_score,
            "classAvg": class_avg,
            "rank": rank,
            "date": batch.create_time.strftime("%Y-%m-%d") if batch.create_time else "",
        })

    return {"records": records}
