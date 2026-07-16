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

    - admin：全部放行
    - teacher：course_id 有值时校验是否为授课教师
    - student：student_id 有值时校验是否为本人；否则拒绝
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "admin":
        return

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
    - 管理员：全部
    - 任课教师：自己授课课程的学生
    - 学生：仅可查自己的评价
    """
    _check_eval_self_or_course(session, current_user, course_id, student_id)

    # Unwrap Query params（直接 Python 调用兼容）
    _student_id = student_id if not isinstance(student_id, QueryParam) else None
    _eval_level = eval_level if not isinstance(eval_level, QueryParam) else None

    stmt = select(StudentEvaluationResult)
    if course_id:
        stmt = stmt.where(StudentEvaluationResult.course_id == course_id)
    if _student_id:
        stmt = stmt.where(StudentEvaluationResult.student_id == _student_id)
    results = session.exec(stmt).all()

    data = []
    for r in results:
        if _eval_level and r.eval_level != _eval_level:
            continue

        student = session.get(Student, r.student_id)
        course = session.get(Course, r.course_id)

        dim_scores = session.exec(
            select(EvalDimensionScore).where(EvalDimensionScore.eval_id == r.eval_id)
        ).all()
        dimensions = []
        for ds in dim_scores:
            dim = session.get(EvalDimension, ds.dimension_id)
            indexes = session.exec(
                select(EvalIndex).where(EvalIndex.dimension_id == ds.dimension_id)
            ).all()
            weight_sum = round(sum(i.weight for i in indexes), 1) if indexes else 0
            dimensions.append({
                "dimensionId": ds.dimension_id,
                "name": dim.dimension_name if dim else "",
                "score": ds.dimension_score,
                "weight": weight_sum,
            })

        data.append({
            "id": r.eval_id,
            "studentDbId": r.student_id,
            "studentId": student.student_no if student else "",
            "studentName": student.real_name if student else "",
            "targetName": student.real_name if student else "",   # 兼容旧字段
            "targetType": "student",
            "courseId": r.course_id,
            "courseName": course.course_name if course else "",
            "totalScore": r.total_score,
            "grade": r.eval_level,
            "dimensions": dimensions,
        })

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

    权限（Eval.Student.UserValid）：仅管理员和课程授课教师可查看。
    """
    _check_course_access(session, current_user, course_id)

    # Unwrap Query params
    _class_id = class_id if not isinstance(class_id, QueryParam) else None

    stmt = select(StudentEvaluationResult).where(
        StudentEvaluationResult.course_id == course_id
    )
    all_results = session.exec(stmt).all()

    if _class_id:
        class_students = set(session.exec(
            select(Student.student_id).where(Student.class_id == _class_id)
        ).all())
        all_results = [r for r in all_results if r.student_id in class_students]

    if not all_results:
        course = session.get(Course, course_id)
        return {
            "courseId": course_id,
            "courseName": course.course_name if course else "",
            "totalStudents": 0,
            "levelDistribution": {},
            "statistics": {},
            "characteristic": "暂无评价数据",
        }

    scores = [r.total_score for r in all_results]
    n = len(scores)
    mean = sum(scores) / n
    sorted_scores = sorted(scores)
    mid = n // 2
    median = sorted_scores[mid] if n % 2 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
    variance = sum((s - mean) ** 2 for s in scores) / n
    std_dev = variance ** 0.5

    # 等级分布
    level_count = {"优": 0, "良": 0, "中": 0, "差": 0}
    for r in all_results:
        level_count[r.eval_level] = level_count.get(r.eval_level, 0) + 1

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

    course = session.get(Course, course_id)
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
