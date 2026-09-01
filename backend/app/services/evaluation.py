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

import json
from dataclasses import dataclass
from math import isfinite

from sqlmodel import Session, select

from app.models import (
    EvalDimension,
    EvalDimensionScore,
    EvalIndex,
    ExamBatch,
    IndividualScore,
    CourseTestDetail,
    ScoreRecord,
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

DIMENSION_NAME_MAP = {
    "academic": "academic",
    "学业成绩": "academic",
    "学业水平": "academic",
    "attitude": "attitude",
    "学习态度": "attitude",
    "progress": "progress",
    "学习进步": "progress",
    "mastery": "mastery",
    "知识掌握": "mastery",
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


def _score_for_rule(
    session: Session,
    student_id: int,
    course_id: int,
    rule: dict,
    fallback: float,
    profile,
    mastery_score: float,
) -> float:
    """Resolve one configured indicator to a 0-100 score."""
    rule_type = str(rule.get("type", "")).strip().lower()
    if rule_type == "direct":
        batch_type = rule.get("batch_type")
        if not isinstance(batch_type, int):
            return fallback
        batch_ids = session.exec(
            select(ExamBatch.batch_id).where(
                ExamBatch.course_id == course_id,
                ExamBatch.batch_type == batch_type,
            )
        ).all()
        if not batch_ids:
            return fallback

        source = str(rule.get("source", "")).strip().lower()
        scores: list[float] = []
        if source in ("", "score_record"):
            scores.extend(session.exec(
                select(ScoreRecord.score).where(
                    ScoreRecord.student_id == student_id,
                    ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
                )
            ).all())
        if source in ("", "individual_score"):
            scores.extend(session.exec(
                select(IndividualScore.score).where(
                    IndividualScore.student_id == student_id,
                    IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                )
            ).all())
        if source in ("", "course_test_detail"):
            scores.extend(session.exec(
                select(CourseTestDetail.total_score).where(
                    CourseTestDetail.student_id == student_id,
                    CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
                )
            ).all())
        return sum(float(score) for score in scores) / len(scores) if scores else fallback

    if rule_type == "attendance":
        return float(profile.attendance_rate) * 100.0
    if rule_type == "interaction":
        return min(100.0, float(profile.interaction_count) * 10.0)
    if rule_type == "homework":
        return float(profile.homework_rate) * 100.0
    if rule_type == "progress":
        return float(profile.progress_score)
    if rule_type == "mastery":
        return mastery_score
    return fallback


def _configured_dimension_scores(
    session: Session,
    student_id: int,
    course_id: int,
    base_scores: dict[str, float],
    profile,
    mastery_score: float,
) -> dict[str, float]:
    """Apply each dimension's EvalIndex weights to its indicator scores.

    EvalIndex weights are validated per dimension by the configuration API, so
    each configured dimension must total 100%. Invalid or incomplete dimensions
    fall back independently without disabling other valid configuration.
    """
    result = dict(base_scores)
    dimensions = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    for dimension in dimensions:
        key = DIMENSION_NAME_MAP.get(dimension.dimension_name.strip())
        if key is None:
            continue
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dimension.dimension_id)
        ).all()
        if not indexes:
            continue
        weights = [float(index.weight) for index in indexes]
        if any(not isfinite(weight) or weight < 0 for weight in weights):
            continue
        total = sum(weights)
        if abs(total - 100.0) >= 0.01:
            continue

        weighted_score = 0.0
        for index, weight in zip(indexes, weights):
            try:
                rule = json.loads(index.score_rule or "{}")
            except (json.JSONDecodeError, TypeError):
                rule = {}
            indicator_score = _score_for_rule(
                session, student_id, course_id, rule, result[key], profile, mastery_score
            )
            weighted_score += weight / total * indicator_score
        result[key] = round(max(0.0, min(100.0, weighted_score)), 1)
    return result


def compute_evaluation(
    session: Session, student_id: int, course_id: int,
    weights: dict | None = None,
) -> EvaluationResult:
    """综合评价：四维度加权求和 + 等级。

    四维权重取默认权重（或调用方显式传入）；各维度内的指标权重由
    _configured_dimension_scores 按 EvalIndex.score_rule 计算。load_dimension_weights
    仅用于评价配置页展示，不参与评分，避免对维度权重重复归一化。
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    profile = compute_profile(session, student_id, course_id)
    masteries = compute_student_mastery(session, student_id, course_id)
    mastery_score = (
        sum(m.accuracy for m in masteries) / len(masteries)
        if masteries else 60.0
    )

    base_scores = {
        "academic": profile.academic_score,
        "attitude": profile.attitude_score,
        "progress": profile.progress_score,
        "mastery": round(mastery_score, 1),
    }
    dim_scores = _configured_dimension_scores(
        session, student_id, course_id, base_scores, profile, mastery_score
    )

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