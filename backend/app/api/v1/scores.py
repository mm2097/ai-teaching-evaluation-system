"""成绩管理 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.permissions import require_teaching_user
from app.models import (
    ScoreRecord, ExamBatch, Student, Course,
    IndividualScore, CourseTestDetail,
)

router = APIRouter(dependencies=[Depends(require_teaching_user)])


@router.get("/score-records", tags=["成绩管理"])
def list_scores(
    course_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出成绩记录（含新旧表）。"""
    results: list[dict] = []

    # 旧表 ScoreRecord
    stmt = select(ScoreRecord)
    if course_id:
        stmt = stmt.where(ScoreRecord.course_id == course_id)
    if student_id:
        stmt = stmt.where(ScoreRecord.student_id == student_id)
    if batch_id:
        stmt = stmt.where(ScoreRecord.batch_id == batch_id)
    for r in session.exec(stmt).all():
        results.append({
            "score_id": r.score_id,
            "course_id": r.course_id,
            "student_id": r.student_id,
            "batch_id": r.batch_id,
            "score": r.score,
            "is_pass": r.is_pass,
            "remark": r.remark,
            "source": "score_record",
        })

    # 新表 IndividualScore
    istmt = select(IndividualScore)
    if student_id:
        istmt = istmt.where(IndividualScore.student_id == student_id)
    if batch_id:
        istmt = istmt.where(IndividualScore.exam_batch_id == batch_id)
    if course_id:
        # 通过 exam_batch 过滤 course
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            istmt = istmt.where(IndividualScore.exam_batch_id.in_(batch_ids))  # type: ignore[arg-type]
        else:
            istmt = istmt.where(IndividualScore.exam_batch_id == -1)
    for r in session.exec(istmt).all():
        batch = session.get(ExamBatch, r.exam_batch_id)
        results.append({
            "score_id": r.score_id,
            "course_id": batch.course_id if batch else 0,
            "student_id": r.student_id,
            "batch_id": r.exam_batch_id,
            "score": r.score,
            "is_pass": 1 if r.score >= 60 else 0,
            "source": "individual_score",
        })

    # 新表 CourseTestDetail
    ctstmt = select(CourseTestDetail)
    if student_id:
        ctstmt = ctstmt.where(CourseTestDetail.student_id == student_id)
    if batch_id:
        ctstmt = ctstmt.where(CourseTestDetail.exam_batch_id == batch_id)
    if course_id:
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        ).all()
        if batch_ids:
            ctstmt = ctstmt.where(CourseTestDetail.exam_batch_id.in_(batch_ids))  # type: ignore[arg-type]
        else:
            ctstmt = ctstmt.where(CourseTestDetail.exam_batch_id == -1)
    for r in session.exec(ctstmt).all():
        batch = session.get(ExamBatch, r.exam_batch_id)
        results.append({
            "score_id": r.score_id,
            "course_id": batch.course_id if batch else 0,
            "student_id": r.student_id,
            "batch_id": r.exam_batch_id,
            "score": r.total_score,
            "is_pass": 1 if (r.total_score or 0) >= 60 else 0,
            "source": "course_test_detail",
        })

    return results


@router.get("/score-records/student/{student_id}", tags=["成绩管理"])
def get_student_scores(
    student_id: int,
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """获取学生成绩汇总：按课程列出各批次成绩 + 总评。"""
    # 收集所有成绩（新旧表）
    all_records: list[dict] = []

    # 旧表
    stmt = select(ScoreRecord).where(ScoreRecord.student_id == student_id)
    if course_id:
        stmt = stmt.where(ScoreRecord.course_id == course_id)
    for r in session.exec(stmt).all():
        all_records.append({
            "course_id": r.course_id,
            "batch_id": r.batch_id,
            "score": r.score,
            "is_pass": r.is_pass,
        })

    # IndividualScore
    istmt = select(IndividualScore).where(IndividualScore.student_id == student_id)
    for r in session.exec(istmt).all():
        batch = session.get(ExamBatch, r.exam_batch_id)
        if not batch:
            continue
        cid = batch.course_id
        if course_id and cid != course_id:
            continue
        all_records.append({
            "course_id": cid,
            "batch_id": r.exam_batch_id,
            "score": r.score,
            "is_pass": 1 if r.score >= 60 else 0,
        })

    # CourseTestDetail
    ctstmt = select(CourseTestDetail).where(CourseTestDetail.student_id == student_id)
    for r in session.exec(ctstmt).all():
        batch = session.get(ExamBatch, r.exam_batch_id)
        if not batch:
            continue
        cid = batch.course_id
        if course_id and cid != course_id:
            continue
        all_records.append({
            "course_id": cid,
            "batch_id": r.exam_batch_id,
            "score": r.total_score,
            "is_pass": 1 if (r.total_score or 0) >= 60 else 0,
        })

    # 按课程分组
    course_scores: dict[int, list] = {}
    for rec in all_records:
        cid = rec["course_id"]
        if cid not in course_scores:
            course_scores[cid] = []
        batch = session.get(ExamBatch, rec["batch_id"])
        course = session.get(Course, cid)
        course_scores[cid].append({
            "batch_name": batch.batch_name if batch else "",
            "batch_type": batch.batch_type if batch else 0,
            "batch_weight": batch.batch_weight if batch else 0,
            "score": rec["score"],
            "is_pass": rec["is_pass"],
        })

    result = []
    for cid, scores_list in course_scores.items():
        course = session.get(Course, cid)
        total = 0.0
        total_weight = 0.0
        for s in scores_list:
            weight = s["batch_weight"] or 0
            if weight > 0:
                total += s["score"] * weight / 100
                total_weight += weight
        # 若无权重配置，使用简单平均
        if total_weight == 0 and scores_list:
            total = sum(s["score"] for s in scores_list) / len(scores_list)
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
            "semester": b.semester,
            "batch_weight": b.batch_weight,
            "full_score": b.full_score,
        }
        for b in batches
    ]
