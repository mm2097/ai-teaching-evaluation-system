"""D09 学情标签生成（规则模板为主）。

6 个规则标签（阈值可调）：
    稳定型     成绩标准差 < 5
    下滑预警   回归斜率 k < -2
    进步显著   回归斜率 k > 2
    偏科型     某模块 ≥ 85 且另一模块 < 50
    出勤风险   缺勤率 > 15%
    互动积极   互动次数 ≥ 班级 P90

LLM 个性化评语见 algorithm/src/reporter.py（可选增强）。
"""
from __future__ import annotations

import math
from sqlmodel import Session, select

from app.models import (
    AttendanceRecord,
    CourseStudent,
    ExamBatch,
    InteractionRecord,
    ScoreRecord,
)
from app.services.mastery import compute_student_mastery
from app.services.predict import get_student_slope

TAG_CONFIG = {
    "stable_std": 5.0,
    "down_slope": -2.0,
    "up_slope": 2.0,
    "good_module": 85.0,
    "weak_module": 50.0,
    "absence_rate": 0.15,
}


def _score_std(scores: list[float]) -> float:
    n = len(scores)
    if n < 2:
        return 0.0
    mean = sum(scores) / n
    var = sum((s - mean) ** 2 for s in scores) / n
    return math.sqrt(var)


def _interaction_p90(session: Session, course_id: int) -> int:
    """班级互动次数 P90。"""
    sids = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()
    counts = []
    for sid in sids:
        c = sum(
            1 for _ in session.exec(
                select(InteractionRecord).where(
                    InteractionRecord.student_id == sid,
                    InteractionRecord.course_id == course_id,
                    InteractionRecord.type.in_([1, 2, 4]),  # type: ignore
                )
            )
        )
        counts.append(c)
    if not counts:
        return 0
    counts.sort()
    idx = int(len(counts) * 0.9)
    return counts[min(idx, len(counts) - 1)]


def generate_tags(
    session: Session, student_id: int, course_id: int
) -> list[str]:
    """生成该学生的规则标签集合。"""
    tags: list[str] = []

    # 1. 稳定 / 2. 下滑 / 3. 进步（共用回归）
    rows = session.exec(
        select(ScoreRecord, ExamBatch)
        .join(ExamBatch, ScoreRecord.batch_id == ExamBatch.batch_id)
        .where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.course_id == course_id,
        )
        .order_by(ExamBatch.exam_time)
    ).all()
    scores = [float(r[0].score) for r in rows]
    if len(scores) >= 3:
        std = _score_std(scores)
        if std < TAG_CONFIG["stable_std"]:
            tags.append("稳定型")

    slope, _ = get_student_slope(session, student_id, course_id)
    if slope < TAG_CONFIG["down_slope"]:
        tags.append("下滑预警")
    elif slope > TAG_CONFIG["up_slope"]:
        tags.append("进步显著")

    # 4. 偏科
    masteries = compute_student_mastery(session, student_id, course_id)
    module_acc: dict[str, list[float]] = {}
    for m in masteries:
        module_acc.setdefault(m.module_name, []).append(m.accuracy)
    if module_acc:
        avgs = {k: sum(v) / len(v) for k, v in module_acc.items()}
        max_v = max(avgs.values())
        min_v = min(avgs.values())
        if max_v >= TAG_CONFIG["good_module"] and min_v < TAG_CONFIG["weak_module"]:
            tags.append("偏科型")

    # 5. 出勤风险
    atts = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.course_id == course_id,
        )
    ).all()
    if atts:
        absent = sum(1 for r in atts if r.status == 3)
        if absent / len(atts) > TAG_CONFIG["absence_rate"]:
            tags.append("出勤风险")

    # 6. 互动积极
    own_int = sum(
        1 for _ in session.exec(
            select(InteractionRecord).where(
                InteractionRecord.student_id == student_id,
                InteractionRecord.course_id == course_id,
                InteractionRecord.type.in_([1, 2, 4]),  # type: ignore
            )
        )
    )
    p90 = _interaction_p90(session, course_id)
    if p90 > 0 and own_int >= p90:
        tags.append("互动积极")

    # 兜底：一个标签都没有，给个默认
    if not tags:
        tags.append("待观察")
    return tags
