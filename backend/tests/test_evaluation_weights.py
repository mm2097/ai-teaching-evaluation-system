"""评价指标数据库权重接入评分引擎测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models import EvalDimension, EvalIndex, ExamBatch, ScoreRecord
from app.services import evaluation


COURSE_ID = 901


@pytest.fixture
def fixed_dimension_scores(monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "compute_profile",
        lambda session, student_id, course_id: SimpleNamespace(
            academic_score=100.0,
            attitude_score=0.0,
            progress_score=50.0,
            attendance_rate=0.8,
            interaction_count=2,
            homework_rate=0.9,
        ),
    )
    monkeypatch.setattr(
        evaluation,
        "compute_student_mastery",
        lambda session, student_id, course_id: [SimpleNamespace(accuracy=20.0)],
    )


def _add_academic_config(session, midterm_weight: float, final_weight: float) -> None:
    midterm = ExamBatch(
        course_id=COURSE_ID, batch_name="期中考试", batch_type=3,
        semester="test", create_by=1,
    )
    final = ExamBatch(
        course_id=COURSE_ID, batch_name="期末考试", batch_type=4,
        semester="test", create_by=1,
    )
    session.add(midterm)
    session.add(final)
    session.flush()
    session.add(ScoreRecord(
        course_id=COURSE_ID, student_id=1, batch_id=midterm.batch_id,
        score=100, create_by=1,
    ))
    session.add(ScoreRecord(
        course_id=COURSE_ID, student_id=1, batch_id=final.batch_id,
        score=0, create_by=1,
    ))

    dimension = EvalDimension(course_id=COURSE_ID, dimension_name="学业成绩")
    session.add(dimension)
    session.flush()
    session.add(EvalIndex(
        dimension_id=dimension.dimension_id, index_name="期中成绩",
        weight=midterm_weight,
        score_rule='{"type":"direct","source":"score_record","batch_type":3}',
    ))
    session.add(EvalIndex(
        dimension_id=dimension.dimension_id, index_name="期末成绩",
        weight=final_weight,
        score_rule='{"type":"direct","source":"score_record","batch_type":4}',
    ))
    session.commit()


def _remove_config(session) -> None:
    dimensions = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == COURSE_ID)
    ).all()
    for dimension in dimensions:
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dimension.dimension_id)
        ).all()
        for index in indexes:
            session.delete(index)
        session.delete(dimension)

    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == COURSE_ID)
    ).all()
    for batch in batches:
        scores = session.exec(
            select(ScoreRecord).where(ScoreRecord.batch_id == batch.batch_id)
        ).all()
        for score in scores:
            session.delete(score)
        session.delete(batch)
    session.commit()


def test_database_index_weights_affect_dimension_and_total_score(
    session, fixed_dimension_scores,
):
    _add_academic_config(session, midterm_weight=40, final_weight=60)
    try:
        result = evaluation.compute_evaluation(session, 1, COURSE_ID)
        assert result.dimensions["academic"] == 40.0
        assert result.total_score == 27.0

        indexes = session.exec(
            select(EvalIndex).join(EvalDimension).where(
                EvalDimension.course_id == COURSE_ID
            )
        ).all()
        by_name = {index.index_name: index for index in indexes}
        by_name["期中成绩"].weight = 80
        by_name["期末成绩"].weight = 20
        session.commit()

        changed = evaluation.compute_evaluation(session, 1, COURSE_ID)
        assert changed.dimensions["academic"] == 80.0
        assert changed.total_score == 43.0
    finally:
        _remove_config(session)


def test_invalid_dimension_weight_sum_falls_back_independently(
    session, fixed_dimension_scores,
):
    _add_academic_config(session, midterm_weight=40, final_weight=50)
    try:
        result = evaluation.compute_evaluation(session, 1, COURSE_ID)
        assert result.dimensions["academic"] == 100.0
        assert result.total_score == 51.0
    finally:
        _remove_config(session)


def test_explicit_dimension_weights_remain_supported(
    session, fixed_dimension_scores,
):
    _add_academic_config(session, midterm_weight=40, final_weight=60)
    try:
        result = evaluation.compute_evaluation(
            session, 1, COURSE_ID,
            weights={"academic": 0, "attitude": 0, "progress": 0, "mastery": 1},
        )
        assert result.total_score == 20.0
    finally:
        _remove_config(session)
