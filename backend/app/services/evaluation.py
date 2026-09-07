"""D08 学习质量评价聚合（线性加权 + 五档等级）。

默认维度只有两个（学业水平 60% + 学习态度 40%），其余维度由教师自行新增并分配占比。
各维度在综合得分中的占比配置在 EvalDimension.weight，全维度合计 100% 时生效；
合计 != 100% 时回退默认权重（严格不生效）。

等级映射（与综合看板「班级成绩等级分布」、学习质量页「分数段分布」一致）：
    >= 90   优秀
    80-89   良好
    70-79   中等
    60-69   合格
    < 60    不合格
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections import Counter, defaultdict
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
from app.services.profile import ProfileScores, _academic_part_score, compute_profile
from app.services.assessment_types import (
    ACADEMIC_ASSESSMENT_TYPES,
    ASSESSMENT_TYPE_LABELS,
)


ACADEMIC_PART_LABELS = {
    part: ASSESSMENT_TYPE_LABELS[part] for part in ACADEMIC_ASSESSMENT_TYPES
}

DEFAULT_WEIGHTS = {
    "academic": 0.6,
    "attitude": 0.4,
}

CANONICAL_KEYS = ("academic", "attitude", "progress", "mastery")

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
    dimensions: dict     # {canonical key | "custom:{id}": 0-100 分}；canonical 四键恒在
    dimension_weights: dict = field(default_factory=dict)  # 生效占比 {key: 0-1}


def score_to_level(score: float) -> str:
    """综合得分 → 五档评价等级（与看板等级分布、分数段分布口径一致）。"""
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= 70:
        return "中等"
    if score >= 60:
        return "合格"
    return "不合格"


def dimension_key(name: str) -> str | None:
    """维度名 → canonical key（academic/attitude/progress/mastery），未命中返回 None。"""
    compact = (name or "").replace(" ", "")
    for token, key in DIMENSION_NAME_KEYS.items():
        if token in compact:
            return key
    return None


def custom_dimension_key(dimension_id: int) -> str:
    """自定义维度的结果键（与 canonical key 不冲突）。"""
    return f"custom:{dimension_id}"


def load_dimension_weights(session: Session, course_id: int) -> dict[str, float]:
    """从 EvalDimension/EvalIndex 读取课程四维评价权重（仅展示用）。

    规则：每个维度下所有指标 weight 求和，映射到 academic/attitude/progress/mastery，
    再归一化为总和 1。若课程没有可用配置，则返回默认权重。
    """
    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    if not dims:
        return dict(DEFAULT_WEIGHTS)

    raw = {key: 0.0 for key in CANONICAL_KEYS}
    for dim in dims:
        key = dimension_key(dim.dimension_name)
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


def load_dimension_shares(session: Session, course_id: int) -> dict[str, float] | None:
    """读取 EvalDimension.weight 作为各维度在综合得分中的占比。

    全维度合计 = 100% 时返回 {key: 0-1}；合计 != 100%（含未配置任何维度）返回 None，
    由调用方回退默认权重（严格不生效）。
    """
    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    if not dims:
        return None
    raw: dict[str, float] = {}
    for dim in dims:
        key = dimension_key(dim.dimension_name)
        if key is None:
            key = custom_dimension_key(dim.dimension_id or 0)
        raw[key] = raw.get(key, 0.0) + max(0.0, float(dim.weight or 0.0))
    total = sum(raw.values())
    if abs(total - 100.0) >= 0.01:
        return None
    return {key: value / 100.0 for key, value in raw.items()}


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
    if rule_type == "academic_part":
        # 学业水平组成部分（小班讨论/期中/期末/考勤/作业/其他），按批次名称关键字取分
        part = str(rule.get("part", "")).strip().lower()
        value = _academic_part_score(session, student_id, course_id, part)
        return float(value) if value is not None else fallback
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
        return float(profile.interaction_score)
    if rule_type == "homework":
        return float(profile.homework_score)
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

    支持任意维度（canonical 内置维度或自定义维度）：
    - 维度无指标 → 0 分
    - 指标权重合计 != 100% 或含非法权重 → 内置维度回退基础分、自定义维度 0 分
    - 有效配置按权重加权；单个指标无数据时回退该维度基础分（内置）或 0（自定义）
    """
    result = dict(base_scores)
    dimensions = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()
    for dimension in dimensions:
        key = dimension_key(dimension.dimension_name)
        if key is None:
            key = custom_dimension_key(dimension.dimension_id or 0)
            result.setdefault(key, 0.0)  # 自定义维度无基础分兜底
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dimension.dimension_id)
        ).all()
        if not indexes:
            result[key] = 0.0  # 未添加指标 → 默认 0 分
            continue
        weights = [float(index.weight) for index in indexes]
        if any(not isfinite(weight) or weight < 0 for weight in weights):
            continue
        total = sum(weights)
        if abs(total - 100.0) >= 0.01:
            continue

        fallback = result.get(key, 0.0)
        weighted_score = 0.0
        for index, weight in zip(indexes, weights):
            try:
                rule = json.loads(index.score_rule or "{}")
            except (json.JSONDecodeError, TypeError):
                rule = {}
            indicator_score = _score_for_rule(
                session, student_id, course_id, rule, fallback, profile, mastery_score
            )
            weighted_score += weight / total * indicator_score
        result[key] = round(max(0.0, min(100.0, weighted_score)), 1)
    return result


def load_course_eval_scheme(session: Session, course_id: int) -> list[dict]:
    """读取教师为该课程配置的评价维度与指标（名称、权重、计分规则原文）。"""
    dimensions = session.exec(
        select(EvalDimension)
        .where(EvalDimension.course_id == course_id)
        .order_by(EvalDimension.sort_num, EvalDimension.dimension_id)  # type: ignore[arg-type]
    ).all()
    scheme: list[dict] = []
    for dim in dimensions:
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
        ).all()
        scheme.append({
            "id": dim.dimension_id,
            "name": dim.dimension_name,
            "description": dim.description or "",
            "indexes": [
                {
                    "id": idx.index_id,
                    "name": idx.index_name,
                    "weight": float(idx.weight or 0),
                    "score_rule": idx.score_rule or "{}",
                }
                for idx in indexes
            ],
        })
    return scheme


def _parse_score_rule(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def score_eval_scheme_for_student(
    session: Session, student_id: int, course_id: int, scheme: list[dict] | None = None,
    profile: ProfileScores | None = None,
) -> dict:
    """按教师配置的指标规则，给学生打出各维度/指标分（维度名用配置原文）。"""
    from app.services.profile import load_academic_parts

    if scheme is None:
        scheme = load_course_eval_scheme(session, course_id)
    if profile is None:
        profile = compute_profile(session, student_id, course_id)
    masteries = compute_student_mastery(session, student_id, course_id)
    mastery_score = (
        sum(item.accuracy for item in masteries) / len(masteries) if masteries else 60.0
    )
    evaluation = compute_evaluation(session, student_id, course_id, profile=profile)
    radar: dict[str, float] = {}
    filled: list[dict] = []
    for dim in scheme:
        index_rows = []
        weighted = 0.0
        weight_total = sum(float(item["weight"]) for item in dim["indexes"]) or 100.0
        for item in dim["indexes"]:
            rule = _parse_score_rule(item.get("score_rule", "{}"))
            score = round(float(_score_for_rule(
                session, student_id, course_id, rule, 75.0, profile, mastery_score,
            )), 1)
            index_rows.append({
                "id": item["id"],
                "name": item["name"],
                "weight": item["weight"],
                "score": score,
            })
            weighted += float(item["weight"]) / weight_total * score
        dim_score = round(weighted, 1) if dim["indexes"] else None
        if dim_score is not None:
            radar[dim["name"]] = dim_score
        filled.append({
            "id": dim["id"],
            "name": dim["name"],
            "description": dim.get("description") or "",
            "score": dim_score,
            "indexes": index_rows,
        })
    parts = load_academic_parts(session, course_id)
    academic_parts = []
    for part, weight in parts.items():
        value = _academic_part_score(session, student_id, course_id, part)
        academic_parts.append({
            "part": part,
            "name": ACADEMIC_PART_LABELS.get(part, part),
            "weight": weight,
            "score": round(float(value), 1) if value is not None else None,
        })
    return {
        "scheme": filled,
        "radar": radar,
        "academicParts": academic_parts,
        "total": evaluation.total_score,
        "level": evaluation.level,
        "source": "teacher_config",
    }


def class_eval_snapshot(
    session: Session, course_id: int, student_ids: list[int], scheme: list[dict] | None = None,
) -> dict:
    """班级学习质量：维度分优先用已落库的教师方案评价，指标分用学业构成班级均值。"""
    from app.services.profile import load_academic_parts, _academic_part_score

    if scheme is None:
        scheme = load_course_eval_scheme(session, course_id)
    if not student_ids:
        return {
            "scheme": scheme, "radar": {}, "academicParts": [],
            "totals": [], "levelDist": {}, "evalCount": 0, "source": "teacher_config",
        }

    results = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.course_id == course_id,
            StudentEvaluationResult.student_id.in_(student_ids),  # type: ignore[arg-type]
        )
    ).all()
    by_dim: dict[int, list[float]] = defaultdict(list)
    eval_ids = [row.eval_id for row in results if row.eval_id]
    if eval_ids:
        for row in session.exec(
            select(EvalDimensionScore).where(EvalDimensionScore.eval_id.in_(eval_ids))  # type: ignore[arg-type]
        ).all():
            by_dim[int(row.dimension_id)].append(float(row.dimension_score))

    parts = load_academic_parts(session, course_id)
    sample_ids = student_ids[:40]
    academic_parts = []
    part_score_map: dict[str, float | None] = {}
    for part, weight in parts.items():
        values = []
        for sid in sample_ids:
            value = _academic_part_score(session, sid, course_id, part)
            if value is not None:
                values.append(float(value))
        avg = round(sum(values) / len(values), 1) if values else None
        part_score_map[part] = avg
        academic_parts.append({
            "part": part,
            "name": ACADEMIC_PART_LABELS.get(part, part),
            "weight": weight,
            "score": avg,
        })

    radar: dict[str, float] = {}
    filled: list[dict] = []
    for dim in scheme:
        vals = by_dim.get(int(dim["id"] or 0), [])
        dim_score = round(sum(vals) / len(vals), 1) if vals else None
        if dim_score is not None:
            radar[dim["name"]] = dim_score
        index_rows = []
        for item in dim["indexes"]:
            rule = _parse_score_rule(item.get("score_rule", "{}"))
            score = None
            if rule.get("type") == "academic_part":
                score = part_score_map.get(str(rule.get("part", "")).strip().lower())
            index_rows.append({
                "id": item["id"],
                "name": item["name"],
                "weight": item["weight"],
                "score": score,
            })
        filled.append({
            "id": dim["id"],
            "name": dim["name"],
            "description": dim.get("description") or "",
            "score": dim_score,
            "sampleSize": len(vals),
            "indexes": index_rows,
        })
    totals = [float(row.total_score) for row in results]
    return {
        "scheme": filled,
        "radar": radar,
        "academicParts": academic_parts,
        "totals": totals,
        "levelDist": dict(Counter(row.eval_level for row in results)),
        "evalCount": len(results),
        "source": "teacher_config",
    }


def compute_evaluation(
    session: Session, student_id: int, course_id: int,
    weights: dict | None = None,
    class_slopes: list[float] | None = None,
    profile: ProfileScores | None = None,
) -> EvaluationResult:
    """综合评价：各维度按占比加权求和 + 五档等级。

    维度占比取 EvalDimension.weight 配置（合计 = 100% 时生效，严格不生效：
    合计 != 100% 回退默认权重 学业水平 60% / 学习态度 40%）；weights 参数
    显式传入时优先使用（兼容旧调用/测试）。各维度内的指标权重由
    _configured_dimension_scores 按 EvalIndex.score_rule 计算。

    class_slopes 供批量计算复用（profile.compute_class_slopes 的结果）；
    profile 供调用方传入已算好的画像，避免重复计算。
    二者缺省时由 compute_profile 实时计算。
    """
    if weights:
        w = {**DEFAULT_WEIGHTS, **weights}
    else:
        shares = load_dimension_shares(session, course_id)
        w = shares if shares is not None else dict(DEFAULT_WEIGHTS)

    if profile is None:
        if class_slopes is None:
            profile = compute_profile(session, student_id, course_id)
        else:
            profile = compute_profile(session, student_id, course_id, class_slopes=class_slopes)
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

    total = sum(w[key] * dim_scores.get(key, 0.0) for key in w)
    total = max(0.0, min(100.0, total))
    return EvaluationResult(
        total_score=round(total, 1),
        level=score_to_level(total),
        dimensions=dim_scores,
        dimension_weights=w,
    )


def persist_evaluation(
    session: Session, student_id: int, course_id: int,
    result: EvaluationResult | None = None,
    class_slopes: list[float] | None = None,
) -> int:
    """落库：写入 student_evaluation_result + eval_dimension_score。返回 eval_id。

    遍历课程的全部配置维度（含自定义维度）写维度分；未配置维度时只写总分。
    """
    if result is None:
        result = compute_evaluation(session, student_id, course_id, class_slopes=class_slopes)

    dims = session.exec(
        select(EvalDimension).where(EvalDimension.course_id == course_id)
    ).all()

    old = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.student_id == student_id,
            StudentEvaluationResult.course_id == course_id,
        )
    ).all()
    old_ids = [o.eval_id for o in old if o.eval_id is not None]
    if old_ids:
        # 先清孤儿维度分，避免重算累积重复行
        for ds in session.exec(
            select(EvalDimensionScore).where(EvalDimensionScore.eval_id.in_(old_ids))  # type: ignore[arg-type]
        ).all():
            session.delete(ds)
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

    # 维度分落库：遍历全部配置维度（键 = canonical key 或 custom:{id}）
    for d in dims:
        key = dimension_key(d.dimension_name) or custom_dimension_key(d.dimension_id or 0)
        session.add(EvalDimensionScore(
            eval_id=er.eval_id,  # type: ignore[arg-type]
            dimension_id=d.dimension_id,
            dimension_score=result.dimensions.get(key, 0.0),
        ))
    session.commit()
    return er.eval_id  # type: ignore[return-value]
