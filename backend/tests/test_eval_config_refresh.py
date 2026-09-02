"""评价配置变化后自动重算画像与学习质量评价的回归测试。

Bug 背景：教师修改「学习态度」中考勤/课堂参与的占比后，
「学生学习质量评价」页面的维度得分不变化——该页读的是持久化表
（student_evaluation_result / eval_dimension_score），而权重保存接口
不会触发重算。修复后配置变更会防抖触发 refresh_course_evaluations。
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select

from app.api.v1 import eval_config
from app.models import (
    AttendanceRecord,
    Course,
    CourseStudent,
    EvalDimension,
    EvalDimensionScore,
    EvalIndex,
    ExamBatch,
    ParticipationSheet,
    StudentEvaluationResult,
    StudentProfile,
    SysUser,
)
from app.services import evaluation
from app.services.analysis_refresh import refresh_course_evaluations
from app.services.profile import compute_class_slopes


COURSE_ID = 902


def _user(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


@pytest.fixture
def attitude_config(session):
    """课程 902：3 名学生 + 考勤/课堂参与数据 + 学习态度维度（50/50）。

    到课率：学生1 0.25（缺勤多）、学生2 1.0、学生3 0.75（一次迟到）
    课堂参与度：学生1 0.5、学生2 1.0、学生3 无数据（基线 0.9）
    """
    session.add(Course(course_id=COURSE_ID, course_code="T902", course_name="测试课",
                       teacher_id=1, semester="2024-2025-1", college="计算机学院"))
    batch = ExamBatch(course_id=COURSE_ID, batch_name="课堂记录", batch_type=5,
                      semester="2024-2025-1", create_by=1)
    session.add(batch)
    session.commit()
    for sid in (1, 2, 3):
        session.add(CourseStudent(course_id=COURSE_ID, student_id=sid))
    session.add_all([
        AttendanceRecord(course_id=COURSE_ID, student_id=1, attendance_date=date(2024, 9, 5), status=0, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=1, attendance_date=date(2024, 9, 12), status=3, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=1, attendance_date=date(2024, 9, 19), status=3, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=1, attendance_date=date(2024, 9, 26), status=3, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=2, attendance_date=date(2024, 9, 5), status=0, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=2, attendance_date=date(2024, 9, 12), status=0, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=3, attendance_date=date(2024, 9, 5), status=0, create_by=1),
        AttendanceRecord(course_id=COURSE_ID, student_id=3, attendance_date=date(2024, 9, 12), status=1, create_by=1),
    ])
    session.add(ParticipationSheet(student_id=1, exam_batch_id=batch.batch_id,
                                   participation_rate=0.5, create_by=1))
    session.add(ParticipationSheet(student_id=2, exam_batch_id=batch.batch_id,
                                   participation_rate=1.0, create_by=1))
    dim = EvalDimension(course_id=COURSE_ID, dimension_name="学习态度", sort_num=1)
    session.add(dim)
    session.commit()
    session.add(EvalIndex(dimension_id=dim.dimension_id, index_name="出勤率", weight=50,
                          score_rule='{"type":"attendance","full_score":100}'))
    session.add(EvalIndex(dimension_id=dim.dimension_id, index_name="课堂参与", weight=50,
                          score_rule='{"type":"interaction","full_score":100}'))
    session.commit()

    yield dim

    # 清理（共享内存库，避免污染其他测试）
    for idx in session.exec(select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)).all():
        session.delete(idx)
    session.delete(dim)
    for ds in session.exec(
        select(EvalDimensionScore).join(
            EvalDimension, EvalDimension.dimension_id == EvalDimensionScore.dimension_id
        ).where(EvalDimension.course_id == COURSE_ID)
    ).all():
        session.delete(ds)
    for er in session.exec(select(StudentEvaluationResult).where(StudentEvaluationResult.course_id == COURSE_ID)).all():
        session.delete(er)
    for p in session.exec(select(StudentProfile).where(StudentProfile.course_id == COURSE_ID)).all():
        session.delete(p)
    for cs in session.exec(select(CourseStudent).where(CourseStudent.course_id == COURSE_ID)).all():
        session.delete(cs)
    for att in session.exec(select(AttendanceRecord).where(AttendanceRecord.course_id == COURSE_ID)).all():
        session.delete(att)
    for sheet in session.exec(select(ParticipationSheet).where(ParticipationSheet.exam_batch_id == batch.batch_id)).all():
        session.delete(sheet)
    for b in session.exec(select(ExamBatch).where(ExamBatch.course_id == COURSE_ID)).all():
        session.delete(b)
    course = session.get(Course, COURSE_ID)
    if course:
        session.delete(course)
    session.commit()


def _read_attitude_and_total(session, dim_id: int, student_id: int) -> tuple[float, float]:
    """读取持久化的学习态度维度分与综合评价总分。"""
    er = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.course_id == COURSE_ID,
            StudentEvaluationResult.student_id == student_id,
        )
    ).first()
    assert er is not None, "评价结果未持久化"
    ds = session.exec(
        select(EvalDimensionScore).where(
            EvalDimensionScore.eval_id == er.eval_id,
            EvalDimensionScore.dimension_id == dim_id,
        )
    ).first()
    assert ds is not None, "学习态度维度分未持久化"
    return ds.dimension_score, er.total_score


def test_weight_change_refreshes_persisted_attitude_score(session, attitude_config, monkeypatch):
    """回归：修改考勤/课堂参与权重后，持久化的学习态度得分与总分随之变化。"""
    # 防抖调度替换为同步执行，便于断言（真实场景为后台线程）
    monkeypatch.setattr(
        eval_config, "_schedule_evaluation_refresh",
        lambda course_id: refresh_course_evaluations(session, course_id),
    )

    refresh_course_evaluations(session, COURSE_ID)
    attitude_before, total_before = _read_attitude_and_total(
        session, attitude_config.dimension_id, 1
    )
    # 学生1：0.5×25（到课率）+ 0.5×50（参与度）= 37.5
    assert attitude_before == 37.5

    indexes = session.exec(
        select(EvalIndex).where(EvalIndex.dimension_id == attitude_config.dimension_id)
    ).all()
    by_name = {i.index_name: i for i in indexes}

    # 与前端保存流程一致：先降（课堂参与 50→0）后升（出勤率 50→100），避免中间态超 100 被拒
    eval_config.update_index(
        index_id=by_name["课堂参与"].index_id, weight=0,
        session=session, current_user=_user(session, 1),
    )
    eval_config.update_index(
        index_id=by_name["出勤率"].index_id, weight=100,
        session=session, current_user=_user(session, 1),
    )

    attitude_after, total_after = _read_attitude_and_total(
        session, attitude_config.dimension_id, 1
    )
    # 学生1：100%×25 = 25.0（课堂参与不再计入）
    assert attitude_after == 25.0
    assert attitude_after != attitude_before
    # 总分变化 = 学习态度默认权重 0.2 × 维度分变化
    assert total_after == round(total_before + 0.2 * (attitude_after - attitude_before), 1)


def test_config_changes_debounce_into_single_refresh(monkeypatch):
    """连续保存多个指标权重只触发一次后台重算（旧的定时器被取消）。"""
    import threading

    timers: list = []

    class FakeTimer:
        def __init__(self, delay: float, fn, args=()):
            self.delay = delay
            self.fn = fn
            self.args = args
            self.cancelled = False
            timers.append(self)

        def start(self) -> None:
            pass

        def cancel(self) -> None:
            self.cancelled = True

    monkeypatch.setattr(threading, "Timer", FakeTimer)
    try:
        eval_config._schedule_evaluation_refresh(COURSE_ID)
        eval_config._schedule_evaluation_refresh(COURSE_ID)

        assert len(timers) == 2
        assert timers[0].cancelled is True
        assert timers[1].cancelled is False
        assert timers[1].delay == eval_config._eval_refresh_delay
    finally:
        eval_config._eval_refresh_timers.clear()


def test_class_slopes_precompute_matches_realtime(session):
    """批量复用班级斜率分布与实时收集的结果一致。"""
    default = evaluation.compute_evaluation(session, 1, 1)
    with_slopes = evaluation.compute_evaluation(
        session, 1, 1, class_slopes=compute_class_slopes(session, 1)
    )
    assert with_slopes.total_score == default.total_score
    assert with_slopes.dimensions == default.dimensions
