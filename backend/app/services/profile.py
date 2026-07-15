"""D02 学业水平 + D03 学习态度 + D04 学习进步 三维度画像。

所有函数输入 (session, student_id, course_id)，返回 0-100 分。
- D02：Z-score 标准化（按 batch 维度计算均值/标准差），近期权重高
- D03：出勤 0.5 + 互动 0.3 + 作业 0.2
- D04：复用 predict.slope_to_progress_score
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.models import (
    AttendanceRecord,
    AttendanceSheet,
    CourseStudent,
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    InteractionRecord,
    ScoreRecord,
    Student,
)
from app.services.predict import (
    get_student_slope,
    slope_to_progress_score,
)


@dataclass
class ProfileScores:
    """学情画像三维度结果。"""

    academic_score: float       # D02
    attitude_score: float       # D03
    progress_score: float       # D04
    attendance_rate: float      # 出勤率 0-1（D03 子项）
    interaction_count: int      # 互动次数（D03 子项）
    homework_rate: float        # 作业提交率 0-1（D03 子项）


# ===== D02 学业水平 =====

def compute_academic_score(
    session: Session, student_id: int, course_id: int
) -> float:
    """Z-score 标准化 + 近期加权映射到百分制。

    流程：
    1. 取学生该课程所有 batch 的成绩（从 ScoreRecord / IndividualScore / CourseTestDetail）
    2. 每个 batch 内，按全班均值/标准差算 z
    3. 多 batch 加权汇总（近期权重高，默认 [0.1,0.2,0.3,0.4]）
    4. 映射回 0-100：score = clamp(75 + 10*z, 0, 100)
    """
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        .order_by(ExamBatch.create_time)
    ).all()

    if not batch_ids:
        return 75.0  # 无数据基线

    z_list: list[float] = []

    def _append_z(student_score: float, class_scores: list[float]) -> None:
        n = len(class_scores)
        if n < 2:
            z_list.append(0.0)
            return
        mean = sum(class_scores) / n
        var = sum((s - mean) ** 2 for s in class_scores) / n
        std = math.sqrt(var) or 1.0
        z = (float(student_score) - mean) / std
        z_list.append(z)

    # 1. ScoreRecord（旧表兼容）
    rows = session.exec(
        select(ScoreRecord, ExamBatch)
        .join(ExamBatch, ScoreRecord.batch_id == ExamBatch.batch_id)
        .where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.batch_id.in_(batch_ids),
        )
        .order_by(ExamBatch.create_time)
    ).all()
    for sr, eb in rows:
        class_scores = session.exec(
            select(ScoreRecord.score).where(ScoreRecord.batch_id == eb.batch_id)
        ).all()
        _append_z(sr.score, class_scores)

    # 2. IndividualScore
    ind_rows = session.exec(
        select(IndividualScore, ExamBatch)
        .join(ExamBatch, IndividualScore.exam_batch_id == ExamBatch.batch_id)
        .where(
            IndividualScore.student_id == student_id,
            IndividualScore.exam_batch_id.in_(batch_ids),
        )
        .order_by(ExamBatch.create_time)
    ).all()
    for isc, eb in ind_rows:
        class_scores = session.exec(
            select(IndividualScore.score).where(
                IndividualScore.exam_batch_id == eb.batch_id
            )
        ).all()
        _append_z(isc.score, class_scores)

    # 3. CourseTestDetail
    dtl_rows = session.exec(
        select(CourseTestDetail, ExamBatch)
        .join(ExamBatch, CourseTestDetail.exam_batch_id == ExamBatch.batch_id)
        .where(
            CourseTestDetail.student_id == student_id,
            CourseTestDetail.exam_batch_id.in_(batch_ids),
        )
        .order_by(ExamBatch.create_time)
    ).all()
    for ctd, eb in dtl_rows:
        class_scores = session.exec(
            select(CourseTestDetail.total_score).where(
                CourseTestDetail.exam_batch_id == eb.batch_id
            )
        ).all()
        _append_z(ctd.total_score, class_scores)

    if not z_list:
        return 75.0

    # 加权（近期权重高）
    n = len(z_list)
    default_w = [0.1, 0.2, 0.3, 0.4]
    if n <= len(default_w):
        weights = default_w[-n:]
        total = sum(weights)
        weights = [w / total for w in weights]
    else:
        weights = [1.0 / n] * n

    z_weighted = sum(w * z for w, z in zip(weights, z_list))
    score = 75.0 + 10.0 * z_weighted
    return max(0.0, min(100.0, score))


# ===== D03 学习态度 =====

def _attendance_rate(session: Session, student_id: int, course_id: int) -> float:
    """出勤率：status=0 计为出勤，其他计为扣分。迟到/早退/请假按半扣。"""
    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.course_id == course_id,
        )
    ).all()
    if not records:
        return 0.9  # 无数据基线 90%
    weights = {0: 1.0, 1: 0.5, 2: 0.5, 3: 0.0, 4: 0.7}
    total = sum(weights.get(r.status, 0.0) for r in records)
    return total / len(records)


def _interaction_score(
    session: Session, student_id: int, course_id: int
) -> tuple[float, int]:
    """互动得分：已禁用（InteractionRecord 废弃）。"""
    return 50.0, 0  # disabled


def _homework_rate(session: Session, student_id: int, course_id: int) -> float:
    """作业提交率：已禁用（InteractionRecord 废弃）。"""
    return 0.9  # disabled


def compute_attitude_score(
    session: Session, student_id: int, course_id: int,
    w_attendance: float = 0.5, w_interaction: float = 0.3, w_homework: float = 0.2,
) -> tuple[float, dict]:
    """D03 学习态度得分 = 0.5*出勤 + 0.3*互动 + 0.2*作业。返回 (score, detail)。"""
    att_rate = _attendance_rate(session, student_id, course_id)
    att_score = att_rate * 100.0

    int_score, int_count = _interaction_score(session, student_id, course_id)
    hw_rate = _homework_rate(session, student_id, course_id)
    hw_score = hw_rate * 100.0

    score = (
        w_attendance * att_score
        + w_interaction * int_score
        + w_homework * hw_score
    )
    detail = {
        "attendance_rate": round(att_rate, 3),
        "attendance_score": round(att_score, 1),
        "interaction_count": int_count,
        "interaction_score": round(int_score, 1),
        "homework_rate": round(hw_rate, 3),
        "homework_score": round(hw_score, 1),
    }
    return max(0.0, min(100.0, score)), detail


# ===== D04 学习进步 =====

def compute_progress_score(
    session: Session, student_id: int, course_id: int
) -> float:
    """D04 学习进步得分：复用回归斜率。

    若班级内有多个学生，按班级斜率分布归一化。
    """
    slope, _ = get_student_slope(session, student_id, course_id)

    # 收集班级所有学生的斜率分布
    course_students = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()
    class_slopes = []
    for sid in course_students:
        k, degraded = get_student_slope(session, sid, course_id)
        if not degraded:
            class_slopes.append(k)

    return slope_to_progress_score(slope, class_slopes if class_slopes else None)


# ===== 汇总 =====

def compute_profile(
    session: Session, student_id: int, course_id: int
) -> ProfileScores:
    """三维度同时计算。"""
    academic = compute_academic_score(session, student_id, course_id)
    attitude, detail = compute_attitude_score(session, student_id, course_id)
    progress = compute_progress_score(session, student_id, course_id)
    return ProfileScores(
        academic_score=round(academic, 1),
        attitude_score=round(attitude, 1),
        progress_score=round(progress, 1),
        attendance_rate=detail["attendance_rate"],
        interaction_count=detail["interaction_count"],
        homework_rate=detail["homework_rate"],
    )
