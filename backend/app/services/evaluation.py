"""D08 学习质量评价聚合（线性加权 + 优良中差双轨）。

四维度默认权重：
    学业成绩（D02）   0.4
    学习态度（D03）   0.2
    学习进步（D04）   0.1
    知识掌握（D05）   0.3

等级映射：
    >= 85  优
    75-85 良
    60-75 中
    < 60  差

课程评价配置中的 EvalIndex.weight 会按维度汇总后归一化为四维权重。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import (
    EvalDimension,
    EvalDimensionScore,
    EvalIndex,
    StudentEvaluationResult,
)
from app.services.mastery import compute_student_mastery
from app.services.profile import compute_profile


DEFAULT_WEIGHTS = {
    "academic": 0.4,
    "attitude": 0.2,
    "progress": 0.1,
    "mastery": 0.3,
}

DIMENSION_NAME_KEYS = {
    "学业成绩": "academic",
    "学业水平": "academic",
    "成绩": "academic",
    "学习态度": "attitude",
    "态度": "attitude",
    "学习进步": "progress",
    "进步": "progress",
    "知识掌握": "mastery",
    "知识点掌握": "mastery",
    "掌握度": "mastery",
}


@dataclass
class EvaluationResult:
    total_score: float
    level: str           # 优 / 良 / 中 / 差
    dimensions: dict     # {academic, attitude, progress, mastery}


def score_to_level(score: float) -> str:
    if score >= 85:
        return "优"
    if score >= 75:
        return "良"
    if score >= 60:
        return "中"
    return "差"


def _dimension_key(name: str) -> str | None:
    compact = (name or "").replace(" ", "")
    for token, key in DIMENSION_NAME_KEYS.items():
        if token in compact:
            return key
    return None


def load_dimension_weights(session: Session, course_id: int) -> dict[str, float]:
    """从 EvalDimension/EvalIndex 读取课程四维评价权重。

    规则：每个维度下所有指标 weight 求和，映射到 academic/attitude/progress/mastery，
    再归一化为总和 1。若课程没有可用配置，则返回默认权重。
    """
    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    if not dims:
        return dict(DEFAULT_WEIGHTS)

    raw = {key: 0.0 for key in DEFAULT_WEIGHTS}
    for dim in dims:
        key = _dimension_key(dim.dimension_name)
        if not key or dim.dimension_id is None:
            continue
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
        ).all()
        weight_sum = sum(max(0.0, float(idx.weight or 0.0)) for idx in indexes)
        raw[key] += weight_sum

    total = sum(raw.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in raw.items()}


def compute_evaluation(
    session: Session, student_id: int, course_id: int,
    weights: dict | None = None,
) -> EvaluationResult:
    """综合评价：四维度加权求和 + 等级。"""
    w = load_dimension_weights(session, course_id) if weights is None else {**DEFAULT_WEIGHTS, **weights}

    profile = compute_profile(session, student_id, course_id)
    masteries = compute_student_mastery(session, student_id, course_id)
    mastery_score = (
        sum(m.accuracy for m in masteries) / len(masteries)
        if masteries else 60.0
    )

    dim_scores = {
        "academic": profile.academic_score,
        "attitude": profile.attitude_score,
        "progress": profile.progress_score,
        "mastery": round(mastery_score, 1),
    }

    total = (
        w["academic"] * dim_scores["academic"]
        + w["attitude"] * dim_scores["attitude"]
        + w["progress"] * dim_scores["progress"]
        + w["mastery"] * dim_scores["mastery"]
    )
    total = max(0.0, min(100.0, total))
    return EvaluationResult(
        total_score=round(total, 1),
        level=score_to_level(total),
        dimensions=dim_scores,
    )


def persist_evaluation(
    session: Session, student_id: int, course_id: int,
    result: EvaluationResult | None = None,
) -> int:
    """落库：写入 student_evaluation_result + eval_dimension_score。返回 eval_id。

    若该课程已配置 EvalDimension（命名匹配"学业成绩/学习态度/学习进步/知识掌握"），
    则把维度分写入 eval_dimension_score；否则只写总分。
    """
    if result is None:
        result = compute_evaluation(session, student_id, course_id)

    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()

    old = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.student_id == student_id,
            StudentEvaluationResult.course_id == course_id,
        )
    ).all()
    for o in old:
        session.delete(o)
    session.commit()

    er = StudentEvaluationResult(
        course_id=course_id,
        student_id=student_id,
        total_score=result.total_score,
        eval_level=result.level,
    )
    session.add(er)
    session.commit()
    session.refresh(er)

    name_to_dim = {d.dimension_name: d for d in dims}
    mapping = [
        ("学业成绩", result.dimensions["academic"]),
        ("学习态度", result.dimensions["attitude"]),
        ("学习进步", result.dimensions["progress"]),
        ("知识掌握", result.dimensions["mastery"]),
    ]
    for name, score in mapping:
        d = name_to_dim.get(name)
        if not d:
            continue
        session.add(EvalDimensionScore(
            eval_id=er.eval_id,  # type: ignore[arg-type]
            dimension_id=d.dimension_id,
            dimension_score=score,
        ))
    session.commit()
    return er.eval_id  # type: ignore[return-value]