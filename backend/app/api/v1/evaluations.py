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
from app.services.evaluation import compute_evaluation, load_dimension_weights

router = APIRouter()


# ============================================================================
# 权限辅助 — 评价查询（学生可查自己，教师可查课程）
# ============================================================================

def _check_eval_self_or_course(
    session: Session,
    current_user: SysUser,
    course_id: int | None,
    student_id: int | None,
) -> None:
    """评价查看权限（Eval.Student.UserValid）。

    - teacher：course_id 有值时校验是否为授课教师
    - student：student_id 有值时校验是否为本人；否则拒绝
    - admin：不参与教学评价
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "teacher":
        if course_id is not None:
            _check_course_access(session, current_user, course_id)
        return

    if role_code == "student":
        if student_id is not None:
            student = session.exec(
                select(Student).where(Student.user_id == current_user.user_id)
            ).first()
            if not student or student.student_id != student_id:
                raise HTTPException(status_code=403, detail="学生仅可查看自己的评价结果")
            return
        # 学生未指定 student_id：在 /results 兜底路径自动补充
        return

    raise HTTPException(status_code=403, detail="无权查看评价数据")


# ============================================================================
# 1. 评价列表（课程/班级级别）
# ============================================================================

# ============================================================================
# 实时评价序列化
# ============================================================================

_DIMENSION_META = [
    ("academic", "学业成绩"),
    ("attitude", "学习态度"),
    ("progress", "学习进步"),
    ("mastery", "知识掌握"),
]


def _dimension_key_from_name(name: str) -> str | None:
    compact = (name or "").replace(" ", "")
    if "学业" in compact or "成绩" in compact:
        return "academic"
    if "态度" in compact:
        return "attitude"
    if "进步" in compact:
        return "progress"
    if "知识" in compact or "掌握" in compact:
        return "mastery"
    return None


def _computed_dimensions(session: Session, course_id: int, result) -> list[dict]:
    weights = load_dimension_weights(session, course_id)
    configured = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    rows: list[dict] = []
    seen: set[str] = set()
    for dim in configured:
        key = _dimension_key_from_name(dim.dimension_name)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({
            "dimensionId": dim.dimension_id or 0,
            "name": dim.dimension_name,
            "score": round(float(result.dimensions.get(key, 0)), 1),
            "weight": round(weights.get(key, 0) * 100, 1),
        })
    for index, (key, name) in enumerate(_DIMENSION_META, start=1):
        if key in seen:
            continue
        rows.append({
            "dimensionId": -index,
            "name": name,
            "score": round(float(result.dimensions.get(key, 0)), 1),
            "weight": round(weights.get(key, 0) * 100, 1),
        })
    return rows


def _evaluation_item_from_algorithm(session: Session, student: Student, course: Course) -> dict:
    result = compute_evaluation(session, student_id=student.student_id, course_id=course.course_id)
    return {
        "id": 0,
        "studentDbId": student.student_id,
        "studentId": student.student_no,
        "studentName": student.real_name,
        "targetName": student.real_name,
        "targetType": "student",
        "courseId": course.course_id,
        "courseName": course.course_name,
        "totalScore": result.total_score,
        "grade": result.level,
        "dimensions": _computed_dimensions(session, course.course_id, result),
        "computed": True,
    }


def _db_dimension_scores(
    session: Session, course_id: int, eval_ids: list[int]
) -> dict[int, list[dict]]:
    """批量读取已落库的维度分，按 eval_id 分组。

    返回 {eval_id: [{dimensionId, name, score, weight}, ...]}。
    维度名来自 EvalDimension；weight 来自 load_dimension_weights（仅展示）。
    """
    if not eval_ids:
        return {}
    rows = session.exec(
        select(EvalDimensionScore, EvalDimension)
        .join(EvalDimension, EvalDimensionScore.dimension_id == EvalDimension.dimension_id, isouter=True)
        .where(EvalDimensionScore.eval_id.in_(eval_ids))  # type: ignore[arg-type]
    ).all()
    weights = load_dimension_weights(session, course_id)
    grouped: dict[int, list[dict]] = {}
    seen: dict[int, set[str]] = {}
    for score_row, dim in rows:
        key = _dimension_key_from_name(dim.dimension_name) if dim else None
        if key and key in seen.setdefault(score_row.eval_id, set()):
            continue
        if key:
            seen[score_row.eval_id].add(key)
        grouped.setdefault(score_row.eval_id, []).append({
            "dimensionId": dim.dimension_id if dim else 0,
            "name": dim.dimension_name if dim else "",
            "score": round(float(score_row.dimension_score), 1),
            "weight": round(weights.get(key, 0) * 100, 1) if key else 0.0,
        })
    # 对落库维度不全的，补齐默认四维（与 _computed_dimensions 一致）
    for eid, items in grouped.items():
        seen_keys = {_dimension_key_from_name(it["name"]) for it in items}
        for index, (key, name) in enumerate(_DIMENSION_META, start=1):
            if key in seen_keys:
                continue
            items.append({
                "dimensionId": -index,
                "name": name,
                "score": 0.0,
                "weight": round(weights.get(key, 0) * 100, 1),
            })
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
    eval_level: str | None = Query(default=None, description="优/良/中/差"),
    student_id: int | None = Query(default=None, description="按数据库 student_id 筛选"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """列出学生评价结果（Eval.Student）。

    权限（Eval.Student.UserValid）：
    - 任课教师：自己授课课程的学生
    - 学生：仅可查自己的评价
    """
    _check_eval_self_or_course(session, current_user, course_id, student_id)

    # Unwrap Query params（直接 Python 调用兼容）
    _student_id = student_id if not isinstance(student_id, QueryParam) else None
    _eval_level = eval_level if not isinstance(eval_level, QueryParam) else None

    _course_id = course_id if not isinstance(course_id, QueryParam) else None
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
            if cached is not None:
                item = _evaluation_item_from_db(
                    session, student, course, cached, db_dims.get(cached.eval_id, [])
                )
            else:
                # 未落库学生实时兜底（单学生约 150ms）
                item = _evaluation_item_from_algorithm(session, student, course)
            if _eval_level and item["grade"] != _eval_level:
                continue
            data.append(item)
        return data

    stmt = select(StudentEvaluationResult)
    if _student_id:
        stmt = stmt.where(StudentEvaluationResult.student_id == _student_id)
    results = session.exec(stmt).all()

    data = []
    for r in results:
        if _eval_level and r.eval_level != _eval_level:
            continue

        student = session.get(Student, r.student_id)
        course = session.get(Course, r.course_id)
        if not student or not course:
            continue

        data.append(_evaluation_item_from_algorithm(session, student, course))

    return data


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
    _check_eval_self_or_course(session, current_user, course_id, student_id)

    # Unwrap Query params
    _student_id = student_id if not isinstance(student_id, QueryParam) else None
    _course_id = course_id if not isinstance(course_id, QueryParam) else None

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
                from app.services.evaluation import compute_evaluation
                ev = compute_evaluation(session, student_id=_student_id, course_id=cs_course_id)
                student = session.get(Student, _student_id)
                return [{
                    "id": 0,
                    "studentId": _student_id,
                    "studentName": student.real_name if student else "",
                    "courseId": cs_course_id,
                    "totalScore": round(ev.total_score, 1),
                    "grade": ev.level,
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

    返回等级分布（优/良/中/差）、分数统计（均值/中位数/标准差/极值），
    支持按班级筛选。

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
            computed_results.append({
                "totalScore": item["totalScore"],
                "grade": item["grade"],
            })

    scores = [r["totalScore"] for r in computed_results]
    n = len(scores)
    mean = sum(scores) / n
    sorted_scores = sorted(scores)
    mid = n // 2
    median = sorted_scores[mid] if n % 2 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
    variance = sum((s - mean) ** 2 for s in scores) / n
    std_dev = variance ** 0.5

    # 等级分布
    level_count = {"优": 0, "良": 0, "中": 0, "差": 0}
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



