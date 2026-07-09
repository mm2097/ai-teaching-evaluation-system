"""评价结果 API。"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import (
    StudentEvaluationResult, EvalDimensionScore,
    Student, Course, EvalDimension,
)

router = APIRouter()


@router.get("/evaluations", tags=["评价管理"])
def list_evaluations(
    course_id: int | None = Query(default=None),
    eval_level: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出学生评价结果。"""
    stmt = select(StudentEvaluationResult)
    if course_id:
        stmt = stmt.where(StudentEvaluationResult.course_id == course_id)
    results = session.exec(stmt).all()

    data = []
    for r in results:
        if eval_level and r.eval_level != eval_level:
            continue

        student = session.get(Student, r.student_id)
        course = session.get(Course, r.course_id)

        # 维度得分
        dim_scores = session.exec(
            select(EvalDimensionScore).where(EvalDimensionScore.eval_id == r.eval_id)
        ).all()
        dimensions = []
        for ds in dim_scores:
            dim = session.get(EvalDimension, ds.dimension_id)
            dimensions.append({
                "name": dim.dimension_name if dim else "",
                "score": ds.dimension_score,
                "weight": 0,  # 可扩展
            })

        data.append({
            "id": r.eval_id,
            "targetName": student.real_name if student else "",
            "targetType": "student",
            "totalScore": r.total_score,
            "grade": r.eval_level,
            "dimensions": dimensions,
        })

    return data


@router.get("/evaluations/results", tags=["评价管理"])
def list_evaluation_results(
    student_id: int | None = Query(default=None),
    dept_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """学生评价结果（按时间正序，前端取最后一条作为最新）。

    前端 StudentEvalView.vue 调用，返回 total_score / grade。
    若数据库无评价结果，则用算法层实时计算兜底。
    """
    stmt = select(StudentEvaluationResult)
    if student_id:
        stmt = stmt.where(StudentEvaluationResult.student_id == student_id)
    if course_id:
        stmt = stmt.where(StudentEvaluationResult.course_id == course_id)
    results = session.exec(stmt.order_by(StudentEvaluationResult.eval_id)).all()

    # 数据库有记录 → 直接返回
    if results:
        data = []
        for r in results:
            student = session.get(Student, r.student_id)
            data.append({
                "id": r.eval_id,
                "student_id": r.student_id,
                "student_name": student.real_name if student else "",
                "total_score": r.total_score,
                "grade": r.eval_level,
            })
        return data

    # 数据库无记录 → 算法层实时计算兜底
    if student_id:
        # 找学生关联的第一门课
        from app.models import CourseStudent
        cs = session.exec(
            select(CourseStudent).where(CourseStudent.student_id == student_id).limit(1)
        ).first()
        if cs:
            try:
                from app.services.evaluation import compute_evaluation
                ev = compute_evaluation(session, student_id=student_id, course_id=cs.course_id)
                return [{
                    "id": 0,
                    "student_id": student_id,
                    "student_name": "",
                    "total_score": round(ev.total_score, 1),
                    "grade": ev.level,
                }]
            except Exception:
                return []
    return []
