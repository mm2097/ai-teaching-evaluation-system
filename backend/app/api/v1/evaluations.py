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
