"""成绩管理 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import ScoreRecord, ExamBatch, Student, Course

router = APIRouter()


@router.get("/score-records", tags=["成绩管理"])
def list_scores(
    course_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出成绩记录。"""
    stmt = select(ScoreRecord)
    if course_id:
        stmt = stmt.where(ScoreRecord.course_id == course_id)
    if student_id:
        stmt = stmt.where(ScoreRecord.student_id == student_id)
    if batch_id:
        stmt = stmt.where(ScoreRecord.batch_id == batch_id)
    records = session.exec(stmt).all()

    return [
        {
            "score_id": r.score_id,
            "course_id": r.course_id,
            "student_id": r.student_id,
            "batch_id": r.batch_id,
            "score": r.score,
            "is_pass": r.is_pass,
            "remark": r.remark,
        }
        for r in records
    ]


@router.get("/score-records/student/{student_id}", tags=["成绩管理"])
def get_student_scores(
    student_id: int,
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """获取学生成绩汇总：按课程列出各批次成绩 + 总评。"""
    stmt = select(ScoreRecord).where(ScoreRecord.student_id == student_id)
    if course_id:
        stmt = stmt.where(ScoreRecord.course_id == course_id)
    records = session.exec(stmt).all()

    # 按课程分组
    course_scores: dict[int, list] = {}
    for r in records:
        if r.course_id not in course_scores:
            course_scores[r.course_id] = []
        batch = session.get(ExamBatch, r.batch_id)
        course = session.get(Course, r.course_id)
        course_scores[r.course_id].append({
            "batch_name": batch.batch_name if batch else "",
            "batch_type": batch.batch_type if batch else 0,
            "batch_weight": batch.batch_weight if batch else 0,
            "score": r.score,
            "is_pass": r.is_pass,
        })

    result = []
    for cid, scores_list in course_scores.items():
        course = session.get(Course, cid)
        total = 0.0
        for s in scores_list:
            weight = s["batch_weight"] or 0
            total += s["score"] * weight / 100
        result.append({
            "course_id": cid,
            "course_name": course.course_name if course else "",
            "total_score": round(total, 2),
            "details": scores_list,
        })

    return {"student_id": student_id, "courses": result}


@router.get("/exam-batches", tags=["成绩管理"])
def list_batches(
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出考核批次。"""
    stmt = select(ExamBatch)
    if course_id:
        stmt = stmt.where(ExamBatch.course_id == course_id)
    batches = session.exec(stmt).all()
    return [
        {
            "batch_id": b.batch_id,
            "course_id": b.course_id,
            "batch_name": b.batch_name,
            "batch_type": b.batch_type,
            "batch_weight": b.batch_weight,
            "exam_time": b.exam_time.isoformat() if b.exam_time else None,
            "full_score": b.full_score,
        }
        for b in batches
    ]
