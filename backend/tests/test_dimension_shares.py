"""维度在综合得分中的占比配置测试。

新设计：
- 默认维度只有两个：学业水平 60% + 学习态度 40%
- EvalDimension.weight 配置各维度占比，合计 = 100% 时生效；否则回退默认（严格不生效）
- 维度无指标 → 0 分；指标权重合计 != 100% → 内置维度回退基础分 / 自定义维度 0 分
- 自定义维度（名称不命中 canonical）以 custom:{id} 键参与计算与展示
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models import (
    Course,
    EvalDimension,
    EvalDimensionScore,
    EvalIndex,
    StudentEvaluationResult,
    SysUser,
)
from app.services import evaluation


COURSE_ID = 903


@pytest.fixture
def fixed_profile(monkeypatch):
    """固定画像与掌握度，保证断言可手工推导。"""
    monkeypatch.setattr(
        evaluation,
        "compute_profile",
        lambda session, student_id, course_id, **kwargs: SimpleNamespace(
            academic_score=100.0,
            attitude_score=0.0,
            progress_score=50.0,
            attendance_rate=0.8,
            interaction_count=2,
            homework_rate=0.9,
            interaction_score=30.0,
            homework_score=60.0,
        ),
    )
    monkeypatch.setattr(
        evaluation,
        "compute_student_mastery",
        lambda session, student_id, course_id: [SimpleNamespace(accuracy=20.0)],
    )


@pytest.fixture
def shares_course(session):
    """课程 903：无维度配置（各测试自行添加），用后清理。"""
    session.add(Course(course_id=COURSE_ID, course_code="T903", course_name="占比测试课",
                       teacher_id=1, semester="2024-2025-1", college="计算机学院"))
    session.commit()
    yield
    for ds in session.exec(
        select(EvalDimensionScore).join(
            EvalDimension, EvalDimensionScore.dimension_id == EvalDimension.dimension_id
        ).where(EvalDimension.course_id == COURSE_ID)
    ).all():
        session.delete(ds)
    for er in session.exec(
        select(StudentEvaluationResult).where(StudentEvaluationResult.course_id == COURSE_ID)
    ).all():
        session.delete(er)
    for dim in session.exec(select(EvalDimension).where(EvalDimension.course_id == COURSE_ID)).all():
        for idx in session.exec(select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)).all():
            session.delete(idx)
        session.delete(dim)
    course = session.get(Course, COURSE_ID)
    if course:
        session.delete(course)
    session.commit()


def _add_attitude_with_attendance_interaction(session, weight: float = 0.0) -> EvalDimension:
    """学习态度维度：出勤率 50 / 课堂参与 50（合计 100）。"""
    dim = EvalDimension(course_id=COURSE_ID, dimension_name="学习态度", weight=weight)
    session.add(dim)
    session.commit()
    session.add(EvalIndex(dimension_id=dim.dimension_id, index_name="出勤率", weight=50,
                          score_rule='{"type":"attendance","full_score":100}'))
    session.add(EvalIndex(dimension_id=dim.dimension_id, index_name="课堂参与", weight=50,
                          score_rule='{"type":"interaction","full_score":100}'))
    session.commit()
    return dim


def _add_custom_with_attendance(session, weight: float = 0.0) -> EvalDimension:
    """自定义维度「动手能力」：出勤率指标 100%。"""
    dim = EvalDimension(course_id=COURSE_ID, dimension_name="动手能力", weight=weight)
    session.add(dim)
    session.commit()
    session.add(EvalIndex(dimension_id=dim.dimension_id, index_name="出勤率", weight=100,
                          score_rule='{"type":"attendance","full_score":100}'))
    session.commit()
    return dim


def test_valid_shares_drive_total(session, fixed_profile, shares_course):
    """占比合计 = 100% → 综合得分 = Σ 维度分 × 占比（含自定义维度）。"""
    attitude = _add_attitude_with_attendance_interaction(session, weight=60)
    custom = _add_custom_with_attendance(session, weight=40)

    result = evaluation.compute_evaluation(session, 1, COURSE_ID)
    # 学习态度 = 0.5×80（到课率）+ 0.5×30（参与度）= 55；动手能力 = 80
    assert result.dimensions["attitude"] == 55.0
    assert result.dimensions[f"custom:{custom.dimension_id}"] == 80.0
    # 0.6×55 + 0.4×80 = 65
    assert result.total_score == 65.0
    assert result.dimension_weights == {
        "attitude": 0.6,
        f"custom:{custom.dimension_id}": 0.4,
    }


def test_invalid_shares_fall_back_to_default(session, fixed_profile, shares_course):
    """占比合计 != 100% → 严格不生效，回退默认（学业水平 0.6 / 学习态度 0.4）。"""
    _add_attitude_with_attendance_interaction(session, weight=60)
    custom = _add_custom_with_attendance(session, weight=0)

    result = evaluation.compute_evaluation(session, 1, COURSE_ID)
    # 合计 60 != 100 → 回退默认：0.6×academic(100) + 0.4×attitude(55) = 82
    assert result.total_score == 82.0
    assert result.dimension_weights == {"academic": 0.6, "attitude": 0.4}
    # 自定义维度不参与总分，但得分仍计算（展示用）
    assert result.dimensions[f"custom:{custom.dimension_id}"] == 80.0


def test_dimension_without_indexes_scores_zero(session, fixed_profile, shares_course):
    """未添加指标的维度默认 0 分（含内置维度）。"""
    progress = EvalDimension(course_id=COURSE_ID, dimension_name="学习进步", weight=0)
    custom = EvalDimension(course_id=COURSE_ID, dimension_name="动手能力", weight=0)
    session.add_all([progress, custom])
    session.commit()

    result = evaluation.compute_evaluation(session, 1, COURSE_ID)
    assert result.dimensions["progress"] == 0.0
    assert result.dimensions[f"custom:{custom.dimension_id}"] == 0.0
    # 占比合计 0 → 回退默认：0.6×100 + 0.4×0 = 60
    assert result.total_score == 60.0


def test_invalid_index_weight_sum_falls_back(session, fixed_profile, shares_course):
    """指标权重合计 != 100%：内置维度回退基础分、自定义维度 0 分。"""
    attitude = EvalDimension(course_id=COURSE_ID, dimension_name="学习态度", weight=0)
    custom = EvalDimension(course_id=COURSE_ID, dimension_name="动手能力", weight=0)
    session.add_all([attitude, custom])
    session.commit()
    session.add(EvalIndex(dimension_id=attitude.dimension_id, index_name="出勤率", weight=40,
                          score_rule='{"type":"attendance","full_score":100}'))
    session.add(EvalIndex(dimension_id=attitude.dimension_id, index_name="课堂参与", weight=50,
                          score_rule='{"type":"interaction","full_score":100}'))
    session.add(EvalIndex(dimension_id=custom.dimension_id, index_name="出勤率", weight=90,
                          score_rule='{"type":"attendance","full_score":100}'))
    session.commit()

    result = evaluation.compute_evaluation(session, 1, COURSE_ID)
    assert result.dimensions["attitude"] == 0.0  # 回退基础分（monkeypatch 为 0）
    assert result.dimensions[f"custom:{custom.dimension_id}"] == 0.0
    # 回退默认：0.6×100 + 0.4×0 = 60
    assert result.total_score == 60.0


def test_persist_writes_all_configured_dimensions(session, fixed_profile, shares_course):
    """落库覆盖全部配置维度（含自定义维度）。"""
    attitude = _add_attitude_with_attendance_interaction(session, weight=60)
    custom = _add_custom_with_attendance(session, weight=40)

    evaluation.persist_evaluation(session, student_id=1, course_id=COURSE_ID)

    er = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.course_id == COURSE_ID,
            StudentEvaluationResult.student_id == 1,
        )
    ).first()
    assert er is not None
    rows = session.exec(
        select(EvalDimensionScore).where(EvalDimensionScore.eval_id == er.eval_id)
    ).all()
    by_dim = {r.dimension_id: r.dimension_score for r in rows}
    assert by_dim[attitude.dimension_id] == 55.0
    assert by_dim[custom.dimension_id] == 80.0
    assert len(rows) == 2


def test_dimension_weight_api_validation(session, shares_course, monkeypatch):
    """配置 API：weight 参数、>100 拒绝、合计与有效性返回。"""
    from fastapi import HTTPException

    from app.api.v1 import eval_config

    monkeypatch.setattr(eval_config, "_schedule_evaluation_refresh", lambda course_id: None)
    user = session.get(SysUser, 1)

    created = eval_config.create_dimension(
        course_id=COURSE_ID, dimension_name="实践能力", weight=30,
        session=session, current_user=user,
    )
    assert created["weight"] == 30

    # 合计 0 + 120 > 100 → 拒绝
    with pytest.raises(HTTPException):
        eval_config.update_dimension(
            dimension_id=created["dimensionId"], weight=120,
            session=session, current_user=user,
        )

    config = eval_config.get_eval_config(COURSE_ID, session=session, current_user=user)
    assert config["dimensionWeightSum"] == 30
    assert config["dimensionWeightValid"] is False

    # 其余维度为 0 时 100 可写入（前端强制合计 = 100 才保存）
    updated = eval_config.update_dimension(
        dimension_id=created["dimensionId"], weight=100,
        session=session, current_user=user,
    )
    assert updated["weight"] == 100

    config = eval_config.get_eval_config(COURSE_ID, session=session, current_user=user)
    assert config["dimensionWeightSum"] == 100
    assert config["dimensionWeightValid"] is True
