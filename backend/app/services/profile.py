"""D02 学业水平 + D03 学习态度 + D04 学习进步 三维度画像。

所有函数输入 (session, student_id, course_id)，返回 0-100 分。
- D02 学业水平：按课程考核构成配比加权（教师可调，合计固定 100%）——
    小班讨论（单项成绩）/ 期中考试（各题得分）/ 期末考试（各题得分）/
    考勤（到课率）/ 其他（作业、实验等单项成绩，占比自动补足 100−其余）
- D03：学习态度 = 0.5×考勤(到课率) + 0.5×课堂参与度（内部合计固定 100%）
- D04：复用 predict.slope_to_progress_score
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.models import (
    AttendanceRecord,
    AttendanceSheet,
    CourseStudent,
    CourseTestDetail,
    EvalDimension,
    EvalIndex,
    ExamBatch,
    IndividualScore,
    InteractionRecord,
    ParticipationSheet,
    ScoreRecord,
    Student,
)
from app.services.predict import (
    get_student_slope,
    slope_to_progress_score,
)

# 学业水平组成部分默认配比（合计 100%，教师可在评价配置页调整）
ACADEMIC_PARTS_DEFAULT: dict[str, float] = {
    "discussion": 10.0,   # 小班讨论（单项成绩，成绩名称含"讨论"）
    "midterm": 30.0,      # 期中考试（各题得分，批次名含"期中"）
    "final": 30.0,        # 期末考试（各题得分，批次名含"期末"）
    "attendance": 10.0,   # 考勤（到课率×100）
    "other": 20.0,        # 其他（作业/实验等其余单项成绩，占比自动补足）
}


@dataclass
class ProfileScores:
    """学情画像三维度结果。"""

    academic_score: float       # D02
    attitude_score: float       # D03
    progress_score: float       # D04
    attendance_rate: float      # 到课率 0-1（D03 子项，优先新表 AttendanceSheet）
    interaction_count: int      # 课堂参与次数（D03 子项）
    participation_rate: float   # 课堂参与度 0-1（D03 子项，无数据基线 0.9）
    homework_rate: float        # 作业提交率 0-1（保留字段，暂无作业数据）


# ===== D02 学业水平 =====

def load_academic_parts(session: Session, course_id: int) -> dict[str, float]:
    """读取学业水平各部分配比（来自评价配置 EvalIndex，教师可调）。

    匹配"学业成绩/学业水平"维度下 score_rule 为 academic_part 的指标；
    合计必须为 100%，否则回退默认配比。
    """
    parts: dict[str, float] = {}
    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    for dim in dims:
        if (dim.dimension_name or "").strip() not in ("学业成绩", "学业水平"):
            continue
        for idx in session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
        ).all():
            try:
                rule = json.loads(idx.score_rule or "{}")
            except (json.JSONDecodeError, TypeError):
                rule = {}
            if rule.get("type") == "academic_part":
                part = str(rule.get("part", "")).strip().lower()
                if part in ACADEMIC_PARTS_DEFAULT and part not in parts:
                    parts[part] = float(idx.weight)
    if not parts or abs(sum(parts.values()) - 100.0) >= 0.01:
        return dict(ACADEMIC_PARTS_DEFAULT)
    return parts


def _batch_scores_by_keyword(
    session: Session,
    student_id: int,
    course_id: int,
    keyword: str,
    exclude: tuple[str, ...] = (),
) -> float | None:
    """按批次名关键字取该生成绩均值。

    命中规则：batch_name 含 keyword 且不含 exclude 中任一关键字。
    数据源优先级：各题得分表（CourseTestDetail.total_score）
    → 单项成绩（IndividualScore.score）→ 旧成绩表（ScoreRecord.score）。
    无数据返回 None。
    """
    def _hit(name: str | None) -> bool:
        n = name or ""
        return keyword in n and not any(k in n for k in exclude)

    matched = [
        b for b in session.exec(
            select(ExamBatch).where(ExamBatch.course_id == course_id)
        ).all()
        if _hit(b.batch_name)
    ]
    if not matched:
        return None
    batch_ids = [b.batch_id for b in matched]

    scores = session.exec(
        select(CourseTestDetail.total_score).where(
            CourseTestDetail.student_id == student_id,
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    if not scores:
        scores = session.exec(
            select(IndividualScore.score).where(
                IndividualScore.student_id == student_id,
                IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
            )
        ).all()
    if not scores:
        scores = session.exec(
            select(ScoreRecord.score).where(
                ScoreRecord.student_id == student_id,
                ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
            )
        ).all()
    vals = [float(s) for s in scores if s is not None]
    return sum(vals) / len(vals) if vals else None


def _has_attendance_data(session: Session, student_id: int, course_id: int) -> bool:
    """判断该生在该课程是否存在考勤数据（新表 AttendanceSheet 或旧表）。"""
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    has_sheet = session.exec(
        select(AttendanceSheet.score_id).where(
            AttendanceSheet.student_id == student_id,
            AttendanceSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        ).limit(1)
    ).first()
    if has_sheet:
        return True
    has_record = session.exec(
        select(AttendanceRecord.attendance_id).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.course_id == course_id,
        ).limit(1)
    ).first()
    return has_record is not None


def _academic_part_score(
    session: Session, student_id: int, course_id: int, part: str
) -> float | None:
    """学业水平单个组成部分的 0-100 得分；无数据返回 None（由配比归一化处理）。

    组成部分（按批次/成绩名称关键字识别）：
      - discussion 小班讨论：成绩名称含"讨论"（单项成绩）
      - midterm    期中考试：批次名含"期中"（各题得分表优先）
      - final      期末考试：批次名含"期末"（各题得分表优先）
      - attendance 考勤：到课率×100（无考勤数据返回 None）
      - other      其他：作业/实验等其余单项成绩（批次名不含 讨论/期中/期末）
    """
    part = (part or "").strip().lower()
    if part == "discussion":
        return _batch_scores_by_keyword(session, student_id, course_id, "讨论")
    if part == "midterm":
        return _batch_scores_by_keyword(
            session, student_id, course_id, "期中", exclude=("期末",)
        )
    if part == "final":
        return _batch_scores_by_keyword(session, student_id, course_id, "期末")
    if part == "attendance":
        if not _has_attendance_data(session, student_id, course_id):
            return None
        return round(_attendance_rate(session, student_id, course_id) * 100.0, 1)
    if part == "other":
        # 其他（作业/实验等）：批次名不含 讨论/期中/期末 的成绩
        others = [
            b for b in session.exec(
                select(ExamBatch).where(ExamBatch.course_id == course_id)
            ).all()
            if not any(k in (b.batch_name or "") for k in ("讨论", "期中", "期末"))
        ]
        if not others:
            return None
        batch_ids = [b.batch_id for b in others]
        scores = session.exec(
            select(IndividualScore.score).where(
                IndividualScore.student_id == student_id,
                IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
            )
        ).all()
        if not scores:
            scores = session.exec(
                select(ScoreRecord.score).where(
                    ScoreRecord.student_id == student_id,
                    ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
                )
            ).all()
        vals = [float(s) for s in scores if s is not None]
        return sum(vals) / len(vals) if vals else None
    return None


def compute_academic_score(
    session: Session, student_id: int, course_id: int,
    parts: dict[str, float] | None = None,
) -> float:
    """学业水平得分 = Σ(组成部分得分 × 配比)，配比合计固定 100%（教师可调）。

    - 配比来源：评价配置（load_academic_parts），未配置时用默认配比
    - 某部分无数据时，其配比按比例分摊到有数据的部分（归一化）
    - 全部无数据时基线 75 分
    """
    if parts is None:
        parts = load_academic_parts(session, course_id)

    scored: dict[str, float] = {}
    for part, weight in parts.items():
        if weight <= 0:
            continue
        value = _academic_part_score(session, student_id, course_id, part)
        if value is not None:
            scored[part] = float(value)

    if not scored:
        return 75.0  # 无数据基线

    total_weight = sum(parts[p] for p in scored)
    if total_weight <= 0:
        return 75.0
    score = sum(scored[p] * parts[p] for p in scored) / total_weight
    return round(max(0.0, min(100.0, score)), 1)


# ===== D03 学习态度 =====

def _attendance_rate(session: Session, student_id: int, course_id: int) -> float:
    """到课率：优先读新表 AttendanceSheet（上传的考勤数据），旧表 AttendanceRecord 兜底。

    - 新表存在记录时，取到课率（attendance_rate）平均值
    - 旧表按状态权重：status=0 计为出勤，迟到/早退/请假按半扣
    - 无任何数据时基线 90%
    """
    # 新表：AttendanceSheet（含导入时计算的到课率）
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    sheet_rates = session.exec(
        select(AttendanceSheet.attendance_rate).where(
            AttendanceSheet.student_id == student_id,
            AttendanceSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    rates = [r for r in sheet_rates if r is not None]
    if rates:
        return float(sum(rates) / len(rates))

    # 旧表：AttendanceRecord（状态权重）
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


def _participation_rate(
    session: Session, student_id: int, course_id: int
) -> tuple[float, int]:
    """课堂参与度：读 ParticipationSheet（上传的课堂参与数据）。

    返回 (参与度 0-1, 参与课堂次数)。无数据时基线 90%、参与次数 0。
    """
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    sheets = session.exec(
        select(ParticipationSheet).where(
            ParticipationSheet.student_id == student_id,
            ParticipationSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    if not sheets:
        return 0.9, 0
    rates = [s.participation_rate for s in sheets if s.participation_rate is not None]
    participated = sum(
        1 for s in sheets for i in range(1, 33)
        if getattr(s, f"participation_{i}") == "是"
    )
    rate = sum(rates) / len(rates) if rates else 0.9
    return float(rate), participated


def _interaction_score(
    session: Session, student_id: int, course_id: int
) -> tuple[float, int]:
    """互动得分：依据课堂参与度（ParticipationSheet，0-1 → 0-100）。

    InteractionRecord 已废弃，课堂互动数据源统一为上传的课堂参与情况表。
    """
    rate, count = _participation_rate(session, student_id, course_id)
    return rate * 100.0, count


def _homework_rate(session: Session, student_id: int, course_id: int) -> float:
    """作业提交率：暂无独立作业数据源，保留字段返回基线 90%。"""
    return 0.9


def _attitude_component_weights(
    session: Session, course_id: int,
    default_attendance: float,
    default_interaction: float,
    default_homework: float,
) -> tuple[float, float, float]:
    """从学习态度维度的指标名推导出勤/互动/作业子权重。"""
    dim = session.exec(
        select(EvalDimension).where(
            EvalDimension.course_id == course_id,
            EvalDimension.dimension_name.contains("态度"),
        )
    ).first()
    if not dim or dim.dimension_id is None:
        return default_attendance, default_interaction, default_homework

    raw = {"attendance": 0.0, "interaction": 0.0, "homework": 0.0}
    indexes = session.exec(
        select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
    ).all()
    for idx in indexes:
        name = (idx.index_name or "").replace(" ", "")
        weight = max(0.0, float(idx.weight or 0.0))
        if "出勤" in name or "考勤" in name:
            raw["attendance"] += weight
        elif "作业" in name:
            raw["homework"] += weight
        elif "互动" in name or "参与" in name or "课堂" in name:
            raw["interaction"] += weight

    total = sum(raw.values())
    if total <= 0:
        return default_attendance, default_interaction, default_homework
    return raw["attendance"] / total, raw["interaction"] / total, raw["homework"] / total


def compute_attitude_score(
    session: Session, student_id: int, course_id: int,
    w_attendance: float = 0.5, w_interaction: float = 0.5, w_homework: float = 0.0,
) -> tuple[float, dict]:
    """D03 学习态度得分 = w_attendance×到课率 + w_interaction×课堂参与度 + w_homework×作业提交率。

    默认 0.5/0.5/0.0（出勤/互动/作业）。学情画像用此默认值；综合评价引擎
    （evaluation._configured_dimension_scores）另按 EvalIndex.score_rule 计算，
    两条链路独立，互不覆盖。
    """
    att_rate = _attendance_rate(session, student_id, course_id)
    att_score = att_rate * 100.0

    int_score, int_count = _interaction_score(session, student_id, course_id)
    part_rate, _ = _participation_rate(session, student_id, course_id)
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
        "participation_rate": round(part_rate, 3),
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
        participation_rate=detail["participation_rate"],
        homework_rate=detail["homework_rate"],
    )
