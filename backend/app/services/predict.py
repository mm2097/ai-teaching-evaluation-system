"""D01 成绩预测 + D04 学习进步（共用回归内核）。

实现：一元线性回归（最小二乘），无第三方依赖。
- 数据点 ≥ 3：用回归给出下一次点估计 + 95% 置信区间 + 斜率。
- 数据点 < 3：降级为"最近一次 ± 标准差"，degraded=True。

斜率复用于 D04 学习进步得分，见 ``slope_to_progress_score``。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    ScoreRecord,
)


@dataclass
class RegressionResult:
    """一元线性回归结果。"""

    slope: float           # 斜率 k，>0 进步、<0 退步
    intercept: float       # 截距 b
    r_squared: float       # 决定系数 0~1
    residual_std: float    # 残差标准差 σ
    next_predict: float    # 下一次点估计
    ci_low: float          # 95% 置信区间下界（已 clamp 0-100）
    ci_high: float         # 95% 置信区间上界（已 clamp 0-100）
    degraded: bool         # True=数据不足降级


def simple_linear_regression(xs: list[float], ys: list[float]) -> RegressionResult:
    """对 (xs, ys) 做一元线性回归。

    返回 RegressionResult。n<3 时降级。
    """
    n = len(xs)
    if n == 0:
        return RegressionResult(0.0, 70.0, 0.0, 5.0, 70.0, 65.0, 75.0, True)

    if n < 3:
        recent = ys[-1]
        std = (sum((y - recent) ** 2 for y in ys) / n) ** 0.5 if n > 1 else 5.0
        std = max(std, 1.0)
        return RegressionResult(
            slope=0.0,
            intercept=recent,
            r_squared=0.0,
            residual_std=std,
            next_predict=recent,
            ci_low=max(0.0, recent - 1.96 * std),
            ci_high=min(100.0, recent + 1.96 * std),
            degraded=True,
        )

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den != 0 else 0.0
    intercept = mean_y - slope * mean_x

    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0.0
    sigma = (ss_res / (n - 2)) ** 0.5 if n > 2 else 0.0

    x_next = max(xs) + 1
    y_next = slope * x_next + intercept
    return RegressionResult(
        slope=slope,
        intercept=intercept,
        r_squared=max(0.0, min(1.0, r_squared)),
        residual_std=sigma,
        next_predict=y_next,
        ci_low=max(0.0, y_next - 1.96 * sigma),
        ci_high=min(100.0, y_next + 1.96 * sigma),
        degraded=False,
    )


def predict_student_scores(
    session: Session, student_id: int, course_id: int
) -> dict:
    """D01 成绩预测：返回前端可直接渲染的字典。

    输出: {current, predicted, trend, confidence, slope, r_squared, degraded, history}
    """
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        .order_by(ExamBatch.create_time)
    ).all()

    # Collect history entries from all three tables
    raw_history: list[dict] = []

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
        raw_history.append({
            "name": eb.batch_name, "score": round(float(sr.score), 1),
            "batch_id": eb.batch_id,
        })

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
        raw_history.append({
            "name": eb.batch_name, "score": round(float(isc.score), 1),
            "batch_id": eb.batch_id,
        })

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
        raw_history.append({
            "name": eb.batch_name, "score": round(float(ctd.total_score), 1),
            "batch_id": eb.batch_id,
        })

    # Sort chronologically by batch_id, then deduplicate by batch_id (first wins)
    raw_history.sort(key=lambda h: h["batch_id"])
    seen: set[int] = set()
    history: list[dict] = []
    for h in raw_history:
        if h["batch_id"] not in seen:
            seen.add(h["batch_id"])
            history.append({"name": h["name"], "score": h["score"]})

    if not history:
        return {
            "current": 70,
            "predicted": "65-75",
            "trend": "稳定",
            "confidence": 50,
            "slope": 0.0,
            "r_squared": 0.0,
            "degraded": True,
            "history": [],
        }

    xs = [float(i + 1) for i in range(len(history))]
    ys = [float(h["score"]) for h in history]

    reg = simple_linear_regression(xs, ys)
    current = ys[-1]
    delta = reg.next_predict - current
    if delta > 1:
        trend = "上升"
    elif delta < -1:
        trend = "下滑"
    else:
        trend = "稳定"

    # 置信度：R² 越高、数据点越多越可信
    confidence = int(
        min(95, 50 + reg.r_squared * 30 + min(len(ys), 5) * 3)
    )

    return {
        "current": round(current, 1),
        "predicted": f"{round(reg.ci_low)}-{round(reg.ci_high)}",
        "predicted_low": round(reg.ci_low),
        "predicted_high": round(reg.ci_high),
        "predicted_mid": round(reg.next_predict, 1),
        "trend": trend,
        "confidence": confidence,
        "slope": round(reg.slope, 2),
        "r_squared": round(reg.r_squared, 2),
        "degraded": reg.degraded,
        "history": history,
    }


def slope_to_progress_score(slope: float, class_slopes: Optional[list[float]] = None) -> float:
    """D04 学习进步得分：把回归斜率映射到 0-100 分。

    - slope > 0 进步；slope < 0 退步
    - 默认基准：slope=0 → 50 分；每 +1 斜率 +10 分；每 -1 斜率 -10 分
    - 若提供班级斜率分布，按 max(|k|) 归一化（更稳健）
    """
    if class_slopes:
        max_abs = max((abs(k) for k in class_slopes), default=1.0)
        max_abs = max(max_abs, 1.0)
        # 归一化到 [-1, 1]，再线性映射到 [0, 100]
        normalized = max(-1.0, min(1.0, slope / max_abs))
        return max(0.0, min(100.0, 50.0 + normalized * 50.0))

    # 默认映射
    return max(0.0, min(100.0, 50.0 + slope * 10.0))


def get_student_slope(
    session: Session, student_id: int, course_id: int
) -> tuple[float, bool]:
    """获取某学生成绩回归斜率（D04 进步分用）。返回 (slope, degraded)。"""
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        .order_by(ExamBatch.create_time)
    ).all()

    # Collect scores from all three tables, deduplicated by batch_id
    seen: set[int] = set()
    ys: list[float] = []

    for bid in batch_ids:
        if bid in seen:
            continue
        # Try ScoreRecord
        sr = session.exec(
            select(ScoreRecord.score).where(
                ScoreRecord.student_id == student_id,
                ScoreRecord.batch_id == bid,
            )
        ).first()
        if sr is not None:
            ys.append(float(sr[0]))
            seen.add(bid)
            continue
        # Try IndividualScore
        isc = session.exec(
            select(IndividualScore.score).where(
                IndividualScore.student_id == student_id,
                IndividualScore.exam_batch_id == bid,
            )
        ).first()
        if isc is not None:
            ys.append(float(isc[0]))
            seen.add(bid)
            continue
        # Try CourseTestDetail
        ctd = session.exec(
            select(CourseTestDetail.total_score).where(
                CourseTestDetail.student_id == student_id,
                CourseTestDetail.exam_batch_id == bid,
            )
        ).first()
        if ctd is not None:
            ys.append(float(ctd[0]))
            seen.add(bid)
            continue

    if len(ys) < 2:
        if ys:
            return 0.0, True
        return 0.0, True

    xs = [float(i + 1) for i in range(len(ys))]
    reg = simple_linear_regression(xs, ys)
    return reg.slope, reg.degraded
