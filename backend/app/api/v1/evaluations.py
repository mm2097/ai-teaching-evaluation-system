"""评价结果 API：学生学习质量评价（Eval.Student）。

数据源仅包含成绩、考勤、课堂互动及教师发布题目的答题数据（不含学生自主练习）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from fastapi.params import Query as QueryParam

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    Course, CourseStudent, EvalDimension, EvalDimensionScore,
    EvalIndex, Student, StudentEvaluationResult, SysRole, SysUser, Teacher,
)
from app.api.v1.analysis import _check_course_access
from app.services.evaluation import (
    ACADEMIC_PART_LABELS,
    DEFAULT_WEIGHTS,
    compute_evaluation,
    custom_dimension_key,
    dimension_key,
    load_dimension_shares,
)
from app.services.profile import _academic_part_score, compute_profile, load_academic_parts

router = APIRouter()


def _academic_parts_for_student(
    session: Session, student_id: int, course_id: int,
) -> list[dict]:
    """返回与评价引擎一致的课程考核构成、权重和学生实际得分。"""
    return [
        {
            "part": part,
            "name": ACADEMIC_PART_LABELS.get(part, part),
            "weight": weight,
            "score": round(float(score), 1) if score is not None else None,
        }
        for part, weight in load_academic_parts(session, course_id).items()
        if (score := _academic_part_score(session, student_id, course_id, part)) is not None
        or weight > 0
    ]


# ============================================================================
# 权限辅助 — 评价查询（学生可查自己，教师可查课程）
# ============================================================================

def _check_eval_self_or_course(
    session: Session,
    current_user: SysUser,
    course_id: int | None,
    student_id: int | None,
) -> int | None:
    """评价查看权限（Eval.Student.UserValid）。

    返回学生角色按登录账号解析出的 student_id（其他角色返回 None），调用方
    应将其作为生效的 student_id 过滤条件：

    - teacher：course_id 有值时校验是否为授课教师；仅传 student_id 时要求该
      学生至少选修了自己的一门课程，防止跨教师越权查询
    - student：student_id 有值时必须为本人；缺省时按登录账号自动解析
    - admin：不参与教学评价
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "teacher":
        if course_id is not None:
            _check_course_access(session, current_user, course_id)
        elif student_id is not None:
            teacher = session.exec(
                select(Teacher).where(Teacher.user_id == current_user.user_id)
            ).first()
            if not teacher:
                raise HTTPException(status_code=403, detail="当前账号未关联教师信息")
            shared = session.exec(
                select(CourseStudent.course_id)
                .join(Course, Course.course_id == CourseStudent.course_id)
                .where(
                    CourseStudent.student_id == student_id,
                    Course.teacher_id == teacher.teacher_id,
                )
            ).first()
            if not shared:
                raise HTTPException(
                    status_code=403,
                    detail="仅可查看自己授课班级学生的评价结果",
                )
        return None

    if role_code == "student":
        student = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not student or student.student_id is None:
            raise HTTPException(status_code=403, detail="当前账号未关联学生信息")
        if student_id is not None and student.student_id != student_id:
            raise HTTPException(status_code=403, detail="学生仅可查看自己的评价结果")
        return student.student_id

    raise HTTPException(status_code=403, detail="无权查看评价数据")


# ============================================================================
# 1. 评价列表（课程/班级级别）
# ============================================================================

# ============================================================================
# 实时评价序列化
# ============================================================================

def _applied_dimension_weights(session: Session, course_id: int) -> dict[str, float]:
    """当前生效的维度占比（0-1）：配置合计=100 用配置，否则回退默认权重（严格不生效）。"""
    shares = load_dimension_shares(session, course_id)
    return shares if shares is not None else dict(DEFAULT_WEIGHTS)


def _computed_dimensions(session: Session, course_id: int, result) -> list[dict]:
    """各维度得分：仅展示配置中的维度（含自定义），无配置时为空列表。"""
    applied = _applied_dimension_weights(session, course_id)
    configured = session.exec(
        select(EvalDimension)
        .where(EvalDimension.course_id == course_id)
        .order_by(EvalDimension.sort_num)
    ).all()
    rows: list[dict] = []
    seen: set[str] = set()
    for dim in configured:
        key = dimension_key(dim.dimension_name) or custom_dimension_key(dim.dimension_id or 0)
        if key in seen:
            continue  # 同名 canonical 维度去重
        seen.add(key)
        if not result.dimension_availability.get(key, True):
            continue
        rows.append({
            "dimensionId": dim.dimension_id or 0,
            "name": dim.dimension_name,
            "score": round(float(result.dimensions.get(key, 0)), 1),
            # 页面展示课程配置占比，而不是缺数据后参与总评的临时归一化占比。
            "weight": round(applied.get(key, 0.0) * 100, 1),
        })
    return rows


def _evaluation_item_from_algorithm(session: Session, student: Student, course: Course) -> dict:
    profile = compute_profile(session, student_id=student.student_id, course_id=course.course_id)
    result = compute_evaluation(
        session, student_id=student.student_id, course_id=course.course_id, profile=profile,
    )
    return {
        "id": 0,
        "studentDbId": student.student_id,
        "studentId": student.student_no,
        "studentName": student.real_name,
        "targetName": student.real_name,
        "targetType": "student",
        "courseId": course.course_id,
        "courseName": course.course_name,
        "totalScore": result.total_score if result.has_data else None,
        "grade": result.level if result.has_data else "—",
        "dimensions": _computed_dimensions(session, course.course_id, result),
        "attitudeDetail": {
            "score": profile.attitude_score,
            "attendanceRate": profile.attendance_rate,
            "attendanceScore": profile.attendance_score,
            "attendanceAvailable": profile.attendance_available,
            "interactionScore": profile.interaction_score,
            "interactionCount": profile.interaction_count,
            "interactionAvailable": profile.interaction_available,
            "homeworkRate": profile.homework_rate,
            "homeworkScore": profile.homework_score,
            "homeworkAvailable": profile.homework_available,
            "homeworkAssignedCount": profile.homework_assigned_count,
            "homeworkSubmittedCount": profile.homework_submitted_count,
            "weights": {
                "attendance": profile.w_attendance,
                "interaction": profile.w_interaction,
                "homework": profile.w_homework,
            },
        },
        "computed": True,
    }


def _db_dimension_scores(
    session: Session, course_id: int, eval_ids: list[int]
) -> dict[int, list[dict]]:
    """批量读取已落库的维度分，按 eval_id 分组。

    返回 {eval_id: [{dimensionId, name, score, weight}, ...]}。
    维度名来自 EvalDimension；weight 为当前生效占比（仅展示）。
    每个 eval_id 覆盖课程的全部配置维度，缺落库行补 score=0。
    """
    if not eval_ids:
        return {}
    applied = _applied_dimension_weights(session, course_id)
    configured = session.exec(
        select(EvalDimension)
        .where(EvalDimension.course_id == course_id)
        .order_by(EvalDimension.sort_num)
    ).all()

    def _entry(dim: EvalDimension, score: float) -> dict:
        key = dimension_key(dim.dimension_name) or custom_dimension_key(dim.dimension_id or 0)
        return {
            "dimensionId": dim.dimension_id or 0,
            "name": dim.dimension_name,
            "score": round(float(score), 1),
            "weight": round(applied.get(key, 0.0) * 100, 1),
        }

    # 每个 eval_id 先补齐全部配置维度（score=0），再用落库行覆盖
    grouped: dict[int, list[dict]] = {
        eid: [_entry(dim, 0.0) for dim in configured] for eid in eval_ids
    }
    rows = session.exec(
        select(EvalDimensionScore, EvalDimension)
        .join(EvalDimension, EvalDimensionScore.dimension_id == EvalDimension.dimension_id, isouter=True)
        .where(EvalDimensionScore.eval_id.in_(eval_ids))  # type: ignore[arg-type]
    ).all()
    seen: dict[int, set[str]] = {}
    for score_row, dim in rows:
        if dim is None:
            continue  # 孤儿行（维度已删除），跳过
        key = dimension_key(dim.dimension_name) or custom_dimension_key(dim.dimension_id or 0)
        if key in seen.setdefault(score_row.eval_id, set()):
            continue
        seen[score_row.eval_id].add(key)
        items = grouped.setdefault(score_row.eval_id, [])
        entry = next((it for it in items if it["dimensionId"] == dim.dimension_id), None)
        if entry is None:
            items.append(_entry(dim, score_row.dimension_score))
        else:
            entry["score"] = round(float(score_row.dimension_score), 1)
    return grouped


def _evaluation_item_from_db(
    session: Session, student: Student, course: Course, result: StudentEvaluationResult,
    dim_scores: list[dict] | None,
) -> dict:
    """用已落库的 StudentEvaluationResult 构造返回项（毫秒级，无需实时计算）。"""
    return {
        "id": result.eval_id or 0,
        "studentDbId": student.student_id,
        "studentId": student.student_no,
        "studentName": student.real_name,
        "targetName": student.real_name,
        "targetType": "student",
        "courseId": course.course_id,
        "courseName": course.course_name,
        "totalScore": result.total_score,
        "grade": result.eval_level,
        "dimensions": dim_scores or [],
        "computed": False,
    }


def _course_students(session: Session, course_id: int, student_id: int | None = None, class_id: int | None = None) -> list[Student]:
    if student_id:
        student = session.get(Student, student_id)
        if not student:
            return []
        enrolled = session.exec(
            select(CourseStudent).where(
                CourseStudent.course_id == course_id,
                CourseStudent.student_id == student_id,
            )
        ).first()
        return [student] if enrolled else []

    enrolled_ids = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()
    if not enrolled_ids:
        return []
    stmt = select(Student).where(Student.student_id.in_(enrolled_ids))  # type: ignore[arg-type]
    if class_id:
        stmt = stmt.where(Student.class_id == class_id)
    return session.exec(stmt.order_by(Student.student_id)).all()

@router.get("/evaluations", tags=["评价管理"])
def list_evaluations(
    course_id: int | None = Query(default=None),
    eval_level: str | None = Query(default=None, description="优秀/良好/中等/合格/不合格"),
    student_id: int | None = Query(default=None, description="按数据库 student_id 筛选"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """列出学生评价结果（Eval.Student）。

    必须指定 course_id 或 student_id，否则 422：无参路径会对全库评价逐行
    实时重算（每行跑一次画像+评价引擎），等同于自我 DoS。

    权限（Eval.Student.UserValid）：
    - 任课教师：自己授课课程的学生
    - 学生：仅可查自己的评价
    """
    # Unwrap Query params（直接 Python 调用兼容）
    _student_id = student_id if not isinstance(student_id, QueryParam) else None
    _eval_level = eval_level if not isinstance(eval_level, QueryParam) else None

    _course_id = course_id if not isinstance(course_id, QueryParam) else None

    resolved_student_id = _check_eval_self_or_course(session, current_user, _course_id, _student_id)
    if resolved_student_id is not None:
        _student_id = resolved_student_id

    if not _course_id and not _student_id:
        raise HTTPException(
            status_code=422,
            detail="必须指定 course_id 或 student_id，不允许全量查询评价结果",
        )

    if _course_id:
        course = session.get(Course, _course_id)
        if not course:
            raise HTTPException(status_code=404, detail="课程不存在")

        students = _course_students(session, _course_id, _student_id)
        if not students:
            return []

        # 优先读已落库的预算结果（毫秒级），避免对全班学生实时重算
        sid_set = [s.student_id for s in students if s.student_id is not None]
        db_rows = session.exec(
            select(StudentEvaluationResult).where(
                StudentEvaluationResult.course_id == _course_id,
                StudentEvaluationResult.student_id.in_(sid_set),  # type: ignore[arg-type]
            )
        ).all()
        db_by_sid = {r.student_id: r for r in db_rows}
        db_dims = _db_dimension_scores(session, _course_id, [r.eval_id for r in db_rows if r.eval_id])

        data: list[dict] = []
        for student in students:
            sid = student.student_id
            cached = db_by_sid.get(sid)
            if _student_id:
                # 学生个人页必须反映当前原始数据，不能使用导入/删除前的评价快照。
                item = _evaluation_item_from_algorithm(session, student, course)
            elif cached is not None:
                item = _evaluation_item_from_db(
                    session, student, course, cached, db_dims.get(cached.eval_id, [])
                )
            else:
                # 未落库学生实时兜底（单学生约 150ms）
                item = _evaluation_item_from_algorithm(session, student, course)
            if _student_id:
                item["academicParts"] = _academic_parts_for_student(
                    session, student.student_id, _course_id,
                )
            if _eval_level and item["grade"] != _eval_level:
                continue
            data.append(item)
        return data

    if _student_id:
        student = session.get(Student, _student_id)
        if not student:
            return []
        enrolled_course_ids = session.exec(
            select(CourseStudent.course_id).where(
                CourseStudent.student_id == _student_id,
                CourseStudent.status == 1,
            )
        ).all()
        courses = session.exec(
            select(Course).where(Course.course_id.in_(enrolled_course_ids))  # type: ignore[arg-type]
        ).all() if enrolled_course_ids else []
        courses.sort(key=lambda item: (item.semester, item.course_name))
        data = []
        for course in courses:
            item = _evaluation_item_from_algorithm(session, student, course)
            item["academicParts"] = _academic_parts_for_student(
                session, _student_id, course.course_id,
            )
            if _eval_level and item["grade"] != _eval_level:
                continue
            data.append(item)
        return data

    # 不可达：course_id / student_id 至少其一有值（入口处已校验）。
    return []


# ============================================================================
# 2. 学生评价结果（含实时兜底）
# ============================================================================

@router.get("/evaluations/results", tags=["评价管理"])
def list_evaluation_results(
    student_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    dept_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """学生评价结果，按时间正序，前端取最后一条为最新（Eval.Student.Score）。

    若数据库无记录，用算法层 compute_evaluation 实时计算兜底。

    权限（Eval.Student.UserValid）：登录用户，学生仅可查自己。
    """
    # Unwrap Query params
    _student_id = student_id if not isinstance(student_id, QueryParam) else None
    _course_id = course_id if not isinstance(course_id, QueryParam) else None

    resolved_student_id = _check_eval_self_or_course(session, current_user, _course_id, _student_id)
    if resolved_student_id is not None:
        _student_id = resolved_student_id

    if not _course_id and not _student_id:
        raise HTTPException(
            status_code=422,
            detail="必须指定 course_id 或 student_id，不允许全量查询评价结果",
        )

    # 个人页必须根据当前成绩/考勤/课堂参与实时计算。持久化评价仅用于
    # 教师班级批量统计，不能在源数据增删改后继续作为学生个人结果返回。
    if _student_id and _course_id:
        student = session.get(Student, _student_id)
        course = session.get(Course, _course_id)
        enrolled = session.exec(
            select(CourseStudent).where(
                CourseStudent.student_id == _student_id,
                CourseStudent.course_id == _course_id,
            )
        ).first()
        if not student or not course or not enrolled:
            return []
        result = compute_evaluation(session, _student_id, _course_id)
        return [{
            "id": 0,
            "studentId": _student_id,
            "studentName": student.real_name,
            "courseId": _course_id,
            "totalScore": result.total_score if result.has_data else None,
            "grade": result.level if result.has_data else "—",
            "computed": True,
        }]

    if _student_id:
        student = session.get(Student, _student_id)
        if not student:
            return []
        enrolled_course_ids = session.exec(
            select(CourseStudent.course_id).where(
                CourseStudent.student_id == _student_id,
                CourseStudent.status == 1,
            )
        ).all()
        courses = session.exec(
            select(Course).where(Course.course_id.in_(enrolled_course_ids))  # type: ignore[arg-type]
        ).all() if enrolled_course_ids else []
        courses.sort(key=lambda item: (item.semester, item.course_name))
        data = []
        for course in courses:
            result = compute_evaluation(session, _student_id, course.course_id)
            data.append({
                "id": 0,
                "studentId": _student_id,
                "studentName": student.real_name,
                "courseId": course.course_id,
                "totalScore": result.total_score if result.has_data else None,
                "grade": result.level if result.has_data else "—",
                "computed": True,
            })
        return data

    stmt = select(StudentEvaluationResult)
    if _student_id:
        stmt = stmt.where(StudentEvaluationResult.student_id == _student_id)
    if _course_id:
        stmt = stmt.where(StudentEvaluationResult.course_id == _course_id)
    results = session.exec(stmt.order_by(StudentEvaluationResult.eval_id)).all()

    if results:
        data = []
        for r in results:
            student = session.get(Student, r.student_id)
            data.append({
                "id": r.eval_id,
                "studentId": r.student_id,
                "studentName": student.real_name if student else "",
                "courseId": r.course_id,
                "totalScore": r.total_score,
                "grade": r.eval_level,
            })
        return data

    # ── 实时计算兜底 ──
    if _student_id:
        cs_course_id = _course_id
        if not cs_course_id:
            cs = session.exec(
                select(CourseStudent)
                .where(CourseStudent.student_id == _student_id)
                .limit(1)
            ).first()
            cs_course_id = cs.course_id if cs else None

        if cs_course_id:
            try:
                ev = compute_evaluation(session, student_id=_student_id, course_id=cs_course_id)
                student = session.get(Student, _student_id)
                return [{
                    "id": 0,
                    "studentId": _student_id,
                    "studentName": student.real_name if student else "",
                    "courseId": cs_course_id,
                    "totalScore": round(ev.total_score, 1) if ev.has_data else None,
                    "grade": ev.level if ev.has_data else "—",
                    "computed": True,
                }]
            except Exception:
                return []
    return []


# ============================================================================
# 3. 班级评价分布统计（Eval.Student.Distribute）
# ============================================================================

@router.get("/evaluations/distribution", tags=["评价管理"])
def get_evaluation_distribution(
    course_id: int = Query(...),
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """班级评价结果分布统计（Eval.Student.Distribute）。

    返回等级分布（优秀/良好/中等/合格/不合格五档，与分数段分布口径一致）、
    分数统计（均值/中位数/标准差/极值），支持按班级筛选。

    权限（Eval.Student.UserValid）：仅课程授课教师可查看。
    """
    _check_course_access(session, current_user, course_id)

    # Unwrap Query params
    _class_id = class_id if not isinstance(class_id, QueryParam) else None

    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    # 优先读已落库的预算总分（毫秒级），未落库学生实时兜底
    students = _course_students(session, course_id, class_id=_class_id)
    if not students:
        return {
            "courseId": course_id,
            "courseName": course.course_name if course else "",
            "totalStudents": 0,
            "levelDistribution": {},
            "statistics": {},
            "characteristic": "暂无评价数据",
        }

    sid_set = [s.student_id for s in students if s.student_id is not None]
    db_rows = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.course_id == course_id,
            StudentEvaluationResult.student_id.in_(sid_set),  # type: ignore[arg-type]
        )
    ).all()
    db_by_sid = {r.student_id: r for r in db_rows}

    computed_results = []
    for student in students:
        sid = student.student_id
        cached = db_by_sid.get(sid)
        if cached is not None:
            computed_results.append({
                "totalScore": cached.total_score,
                "grade": cached.eval_level,
            })
        else:
            item = _evaluation_item_from_algorithm(session, student, course)
            if item["totalScore"] is not None:
                computed_results.append({
                    "totalScore": item["totalScore"],
                    "grade": item["grade"],
                })

    if not computed_results:
        return {
            "courseId": course_id,
            "courseName": course.course_name,
            "totalStudents": 0,
            "levelDistribution": {},
            "statistics": {},
            "characteristic": "暂无评价数据",
        }

    scores = [r["totalScore"] for r in computed_results]
    n = len(scores)
    mean = sum(scores) / n
    sorted_scores = sorted(scores)
    mid = n // 2
    median = sorted_scores[mid] if n % 2 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
    variance = sum((s - mean) ** 2 for s in scores) / n
    std_dev = variance ** 0.5

    # 等级分布（五档，与 scoreDistribution 分数段口径一致）
    level_count = {"优秀": 0, "良好": 0, "中等": 0, "合格": 0, "不合格": 0}
    for r in computed_results:
        level = r["grade"]
        level_count[level] = level_count.get(level, 0) + 1

    level_ratio = {
        k: round(v / n * 100, 1) for k, v in level_count.items()
    }

    # 分数段分布（10 分一档）
    score_buckets = []
    for low in range(0, 100, 10):
        high = low + 9 if low < 90 else 100
        cnt = sum(1 for s in scores if low <= s <= high)
        score_buckets.append({
            "range": f"{low}-{high}",
            "low": low, "high": high,
            "count": cnt,
            "ratio": round(cnt / n * 100, 1),
        })

    # 班级特征
    if std_dev < 8:
        dispersion = "集中（学生质量差异小）"
    elif std_dev > 15:
        dispersion = "分散（两极分化明显）"
    else:
        dispersion = "适中"

    dominant_level = max(level_count, key=level_count.get) if level_count else "无"
    characteristic = f"离散度{dispersion}，主流等级为「{dominant_level}」"

    return {
        "courseId": course_id,
        "courseName": course.course_name if course else "",
        "classId": class_id,
        "totalStudents": n,
        "levelDistribution": level_count,
        "levelRatio": level_ratio,
        "dominantLevel": dominant_level,
        "scoreDistribution": score_buckets,
        "statistics": {
            "mean": round(mean, 1),
            "median": round(median, 1),
            "stdDev": round(std_dev, 1),
            "maxScore": round(max(scores), 1),
            "minScore": round(min(scores), 1),
        },
        "characteristic": characteristic,
    }



