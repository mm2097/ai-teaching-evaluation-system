"""课程目标(CT1-CT8)达成度算法。

三级归因模型（按证据强度递减）：
  1. 知识点精确归因（CT1-CT4，high）：学生各知识点掌握度 → 按 KnowledgePoint.course_objectives 分配到 CT
  2. 试卷大题归因（CT1-CT4，medium）：CourseTestDetail 大题知识点 → 知识点 → CT，与知识点归因融合
  3. 考核批次类型归因（CT4-CT6，medium）：按 ExamBatch.batch_type 查 BATCH_TYPE_CT_WEIGHTS 分配
  4. 素养推断（CT7-CT8，low）：实践成绩 + 考勤 + 课堂参与 组合推断

设计要点：
  - 无证据的 CT 标 None，不计入总体达成度（不强行赋 0 分）。
  - 计算全程 try/except 降级，失败不阻断 analysis_refresh 主流程。
  - 复用 mastery.compute_student_mastery / compute_class_mastery，不重复造轮子。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from app.models import (
    AttendanceSheet,
    CourseStudent,
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    KnowledgeModule,
    KnowledgePoint,
    ParticipationSheet,
    ScoreRecord,
    Student,
    CTAchievement,
)
from app.services.ct_constants import (
    BATCH_TYPE_CT_WEIGHTS,
    CT7_LITERACY_WEIGHTS,
    CT8_LITERACY_WEIGHTS,
    CT_CODES,
    CT_DEFINITIONS,
    degree_to_level,
    parse_ct_field,
)
from app.services.mastery import compute_student_mastery

# 试卷每大题满分（5 大题 × 20 分 = 100 分，与 mastery.EXAM_QUESTION_FULL_SCORE 一致）
_EXAM_Q_FULL = 20.0


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class CTAchievementResult:
    """单学生 CT 达成度计算结果（内存结构，落库前用）。"""
    student_id: int
    course_id: int
    ct_scores: dict[str, float | None] = field(default_factory=dict)      # CT1-CT8 -> 0-100 | None
    ct_confidence: dict[str, str] = field(default_factory=dict)           # CT -> high/medium/low
    overall_score: float = 0.0
    overall_level: str = "—"

    def __post_init__(self):
        if not self.ct_scores:
            self.ct_scores = {ct: None for ct in CT_CODES}

    @property
    def weak_cts(self) -> list[str]:
        """达成度 < 60 的 CT 编号。"""
        return [ct for ct in CT_CODES
                if self.ct_scores.get(ct) is not None and self.ct_scores[ct] < 60]

    @property
    def strong_cts(self) -> list[str]:
        """达成度 ≥ 85 的 CT 编号。"""
        return [ct for ct in CT_CODES
                if self.ct_scores.get(ct) is not None and self.ct_scores[ct] >= 85]

    def to_dict(self) -> dict:
        """前端响应结构。"""
        valid = [s for s in self.ct_scores.values() if s is not None]
        return {
            "ct_scores": {
                ct: {
                    "score": self.ct_scores[ct],
                    "level": degree_to_level(self.ct_scores[ct]) if self.ct_scores[ct] is not None else None,
                    "confidence": self.ct_confidence.get(ct),
                    "desc": CT_DEFINITIONS[ct]["desc"],
                    "category": CT_DEFINITIONS[ct]["category"],
                }
                for ct in CT_CODES
            },
            "overall": {"score": self.overall_score, "level": self.overall_level},
            "weak_cts": self.weak_cts,
            "strong_cts": self.strong_cts,
            "radar": {ct: self.ct_scores[ct] for ct in CT_CODES},
        }


# ============================================================================
# 归因子函数
# ============================================================================

def _knowledge_ct_scores(
    session: Session, student_id: int, course_id: int
) -> tuple[dict[str, float], dict[str, str]]:
    """知识点精确归因（CT1-CT4，high）。

    取学生各知识点掌握度，按 KnowledgePoint.course_objectives 分配到对应 CT。
    返回 (ct_score_map, ct_confidence_map)，仅含有证据的 CT。
    """
    masteries = compute_student_mastery(session, student_id, course_id)
    ct_acc: dict[str, list[float]] = {ct: [] for ct in CT_CODES[:4]}  # CT1-CT4
    for m in masteries:
        kp = session.get(KnowledgePoint, m.point_id)
        if not kp:
            continue
        cts = parse_ct_field(kp.course_objectives)
        for ct in cts:
            if ct in ct_acc:
                ct_acc[ct].append(m.accuracy)
    scores: dict[str, float] = {}
    confidence: dict[str, str] = {}
    for ct, accs in ct_acc.items():
        if accs:
            scores[ct] = round(sum(accs) / len(accs), 1)
            confidence[ct] = "high"
    return scores, confidence


def _test_detail_ct_scores(
    session: Session, student_id: int, course_id: int
) -> dict[str, float]:
    """试卷大题扣分归因（CT1-CT4，medium）。

    CourseTestDetail.questionN_knowledge（文本知识点名）→ 模糊匹配 KnowledgePoint → CT。
    得分率 = (满分 - 扣分) / 满分，按 CT 聚合。
    """
    # 课程知识点名 → CT 列表（含精确名与去空白别名）
    points = _course_points(session, course_id)
    name_to_cts: dict[str, list[str]] = {}
    for p in points:
        cts = parse_ct_field(p.course_objectives)
        if cts:
            name_to_cts[p.point_name.strip()] = cts
    if not name_to_cts:
        return {}

    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    if not batch_ids:
        return {}

    details = session.exec(
        select(CourseTestDetail).where(
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
            CourseTestDetail.student_id == student_id,
        )
    ).all()

    ct_rates: dict[str, list[float]] = {ct: [] for ct in CT_CODES[:4]}
    for d in details:
        for qn in range(1, 6):
            try:
                deduction = float(getattr(d, f"question{qn}_score") or 0)
            except (TypeError, ValueError):
                deduction = 0.0
            knowledge_text = getattr(d, f"question{qn}_knowledge") or ""
            if not knowledge_text:
                continue
            # 知识点文本可能含分隔符（与 mastery 同款拆分逻辑）
            names = _split_knowledge_names(knowledge_text)
            cts_found: list[str] = []
            for name in names:
                if name in name_to_cts:
                    cts_found.extend(name_to_cts[name])
            if not cts_found:
                continue
            rate = max(0.0, (_EXAM_Q_FULL - deduction) / _EXAM_Q_FULL) * 100
            for ct in set(cts_found) & set(ct_rates):
                ct_rates[ct].append(rate)

    return {ct: round(sum(rs) / len(rs), 1) for ct, rs in ct_rates.items() if rs}


def _batch_ct_scores(
    session: Session, student_id: int, course_id: int
) -> dict[str, float]:
    """考核批次类型归因（CT1-CT6，medium）。

    各批次成绩得分率 × BATCH_TYPE_CT_WEIGHTS 中该 batch_type 的 CT 权重，
    多批次按 CT 累加后取加权平均。
    """
    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id)
    ).all()
    if not batches:
        return {}

    batch_ids = [b.batch_id for b in batches]
    batch_type_map = {b.batch_id: b.batch_type for b in batches}
    full_score = 100.0  # ExamBatch.full_score 默认 100

    # 收集该学生各批次成绩（三表去重取最高，与 queries._t_get_score_list 同口径）
    sr = session.exec(
        select(ScoreRecord.batch_id, ScoreRecord.score).where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    ind = session.exec(
        select(IndividualScore.exam_batch_id, IndividualScore.score).where(
            IndividualScore.student_id == student_id,
            IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    ctd = session.exec(
        select(CourseTestDetail.exam_batch_id, CourseTestDetail.total_score).where(
            CourseTestDetail.student_id == student_id,
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    score_map: dict[int, float] = {}
    for bid, sc in sr:
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))
    for bid, sc in ind:
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))
    for bid, sc in ctd:
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))

    # 按 CT 累加（得分率 × 权重），并记录权重和用于加权平均
    ct_weighted_sum: dict[str, float] = {ct: 0.0 for ct in CT_CODES}
    ct_weight_total: dict[str, float] = {ct: 0.0 for ct in CT_CODES}
    for bid, score in score_map.items():
        btype = batch_type_map.get(bid)
        if btype is None:
            continue
        weights = BATCH_TYPE_CT_WEIGHTS.get(btype)
        if not weights:
            continue
        rate = max(0.0, min(100.0, score / full_score * 100))
        for ct, w in weights.items():
            ct_weighted_sum[ct] += rate * w
            ct_weight_total[ct] += w

    return {
        ct: round(ct_weighted_sum[ct] / ct_weight_total[ct], 1)
        for ct in CT_CODES
        if ct_weight_total[ct] > 0
    }


def _literacy_ct_scores(
    session: Session, student_id: int, course_id: int
) -> dict[str, float]:
    """素养类推断（CT7-CT8，low）。

    CT7 ≈ 0.5×实践成绩得分率 + 0.3×考勤率 + 0.2×课堂参与率
    CT8 ≈ 0.6×实践成绩得分率 + 0.4×课堂参与率
    无数据时对应项记 0（素养类必须有兜底值，否则学生无 CT7/CT8 画像）。
    """
    practice_rate = _practice_score_rate(session, student_id, course_id)
    attendance_rate = _attendance_rate(session, student_id, course_id)
    participation_rate = _participation_rate(session, student_id, course_id)

    ct7 = (
        CT7_LITERACY_WEIGHTS["practice"] * practice_rate
        + CT7_LITERACY_WEIGHTS["attendance"] * attendance_rate
        + CT7_LITERACY_WEIGHTS["participation"] * participation_rate
    )
    ct8 = (
        CT8_LITERACY_WEIGHTS["practice"] * practice_rate
        + CT8_LITERACY_WEIGHTS["participation"] * participation_rate
    )
    return {"CT7": round(ct7, 1), "CT8": round(ct8, 1)}


# ============================================================================
# 辅助：数据采集
# ============================================================================

def _course_points(session: Session, course_id: int) -> list[KnowledgePoint]:
    """课程下全部知识点。"""
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_ids = [m.module_id for m in modules]
    if not module_ids:
        return []
    return session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all()


def _split_knowledge_names(text: str | None) -> list[str]:
    """拆分知识点文本（与 knowledge_utils.split_knowledge_names 同口径）。"""
    if not text:
        return []
    import re
    parts = re.split(r"[、,，;；/]", text)
    return [p.strip() for p in parts if p.strip()]


def _practice_score_rate(session: Session, student_id: int, course_id: int) -> float:
    """实践环节（实验 batch_type=2）成绩平均得分率（0-100）。无数据返回 0。"""
    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id, ExamBatch.batch_type == 2)
    ).all()
    if not batches:
        return 0.0
    batch_ids = [b.batch_id for b in batches]
    scores: list[float] = []
    for bid, sc in session.exec(
        select(IndividualScore.exam_batch_id, IndividualScore.score).where(
            IndividualScore.student_id == student_id,
            IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all():
        scores.append(float(sc))
    for bid, sc in session.exec(
        select(ScoreRecord.batch_id, ScoreRecord.score).where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all():
        scores.append(float(sc))
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 1)


def _attendance_rate(session: Session, student_id: int, course_id: int) -> float:
    """考勤率（0-100）。无数据返回 0。"""
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    sheets = session.exec(
        select(AttendanceSheet).where(
            AttendanceSheet.student_id == student_id,
            AttendanceSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    total = sum(s.total_count or 0 for s in sheets)
    present = sum(s.present_count or 0 for s in sheets)
    if not total:
        return 0.0
    return round(present / total * 100, 1)


def _participation_rate(session: Session, student_id: int, course_id: int) -> float:
    """课堂参与率（0-100）。无数据返回 0。"""
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    sheets = session.exec(
        select(ParticipationSheet).where(
            ParticipationSheet.student_id == student_id,
            ParticipationSheet.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all()
    rates = [float(s.participation_rate or 0) * 100 for s in sheets]
    if not rates:
        return 0.0
    return round(sum(rates) / len(rates), 1)


# ============================================================================
# 主算法
# ============================================================================

def compute_student_ct(
    session: Session, student_id: int, course_id: int
) -> CTAchievementResult:
    """单学生 CT1-CT8 达成度（核心算法）。

    归因顺序：
      CT1-CT4：知识点精确归因（high）→ 试卷大题归因融合（medium）→ 批次类型补充
      CT4-CT6：批次类型归因（medium）
      CT7-CT8：素养推断（low）
    """
    result = CTAchievementResult(student_id=student_id, course_id=course_id)
    ct_scores: dict[str, float | None] = {ct: None for ct in CT_CODES}
    ct_confidence: dict[str, str] = {}

    # 1. 知识点精确归因（CT1-CT4，high）
    kp_scores, kp_conf = _knowledge_ct_scores(session, student_id, course_id)
    for ct, sc in kp_scores.items():
        ct_scores[ct] = sc
        ct_confidence[ct] = kp_conf[ct]

    # 2. 试卷大题归因（CT1-CT4）与知识点归因融合
    test_scores = _test_detail_ct_scores(session, student_id, course_id)
    for ct, sc in test_scores.items():
        if ct_scores[ct] is None:
            ct_scores[ct] = sc
            ct_confidence[ct] = "medium"
        else:
            # 知识点掌握度 0.6 + 试卷大题 0.4 加权融合
            ct_scores[ct] = round(ct_scores[ct] * 0.6 + sc * 0.4, 1)
            # 已有 high 置信度，融合后保持 high（知识点归因更精确）

    # 3. 考核批次类型归因（补充 CT1-CT6）
    batch_scores = _batch_ct_scores(session, student_id, course_id)
    for ct, sc in batch_scores.items():
        if ct_scores[ct] is None:
            ct_scores[ct] = sc
            ct_confidence[ct] = "medium"

    # 4. 素养推断（CT7-CT8，low）
    literacy_scores = _literacy_ct_scores(session, student_id, course_id)
    for ct, sc in literacy_scores.items():
        ct_scores[ct] = sc
        ct_confidence[ct] = "low"

    # 总体达成度（仅有证据的 CT 计入均值）
    valid = [s for s in ct_scores.values() if s is not None]
    overall = round(sum(valid) / len(valid), 1) if valid else 0.0

    result.ct_scores = ct_scores
    result.ct_confidence = ct_confidence
    result.overall_score = overall
    result.overall_level = degree_to_level(overall) if valid else "—"
    return result


def compute_class_ct(
    session: Session, course_id: int, class_id: int | None = None
) -> dict:
    """班级 CT 达成度总览。

    返回 {ct_avg, ct_std, ct_pass_rate, weak_cts_class, students}。
    """
    stmt = (
        select(CourseStudent.student_id)
        .join(Student, CourseStudent.student_id == Student.student_id)
        .where(CourseStudent.course_id == course_id)
    )
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    student_ids = list(session.exec(stmt).all())

    per_student: list[tuple[int, CTAchievementResult]] = []
    for sid in student_ids:
        try:
            res = compute_student_ct(session, sid, course_id)
            per_student.append((sid, res))
        except Exception:
            continue

    # 各 CT 全班均值 / 标准差 / 达成率
    ct_avg: dict[str, float] = {}
    ct_std: dict[str, float] = {}
    ct_pass_rate: dict[str, float] = {}
    for ct in CT_CODES:
        vals = [r.ct_scores[ct] for _, r in per_student if r.ct_scores.get(ct) is not None]
        if vals:
            ct_avg[ct] = round(sum(vals) / len(vals), 1)
            mean = ct_avg[ct]
            ct_std[ct] = round(math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals)), 1)
            ct_pass_rate[ct] = round(sum(1 for v in vals if v >= 60) / len(vals), 3)
        else:
            ct_avg[ct] = 0.0
            ct_std[ct] = 0.0
            ct_pass_rate[ct] = 0.0

    # 班级短板：达成率最低或均值 < 60 的 CT
    weak_cts_class = [ct for ct in CT_CODES if ct_avg[ct] < 60 and ct_pass_rate[ct] < 0.6]

    students = [
        {
            "student_id": sid,
            "name": _student_name(session, sid),
            "ct_scores": r.ct_scores,
            "overall": r.overall_score,
            "overall_level": r.overall_level,
            "weak_cts": r.weak_cts,
        }
        for sid, r in per_student
    ]
    return {
        "course_id": course_id,
        "student_count": len(student_ids),
        "ct_avg": ct_avg,
        "ct_std": ct_std,
        "ct_pass_rate": ct_pass_rate,
        "weak_cts_class": weak_cts_class,
        "students": students,
    }


def _student_name(session: Session, student_id: int) -> str:
    stu = session.get(Student, student_id)
    return stu.real_name if stu else ""


# ============================================================================
# 落库
# ============================================================================

def persist_ct_achievement(
    session: Session, student_id: int, course_id: int,
    result: CTAchievementResult | None = None,
) -> int:
    """写入/更新单学生 CT 达成度到 ct_achievement 表。

    联合唯一 (course_id, student_id)：先删旧再插新。
    无任何证据（所有 CT 为 None）时只清理旧记录不写 0 分伪画像。
    """
    if result is None:
        result = compute_student_ct(session, student_id, course_id)

    # 删旧
    for old in session.exec(
        select(CTAchievement).where(
            CTAchievement.course_id == course_id,
            CTAchievement.student_id == student_id,
        )
    ).all():
        session.delete(old)
    session.commit()

    valid = [s for s in result.ct_scores.values() if s is not None]
    if not valid:
        return 0

    # 置信度按 CT1-8 顺序拼成逗号串（None 项留空）
    conf_parts = []
    for ct in CT_CODES:
        c = result.ct_confidence.get(ct)
        conf_parts.append(c or "")
    ct_confidence_str = ",".join(conf_parts) if any(conf_parts) else None

    row = CTAchievement(
        course_id=course_id,
        student_id=student_id,
        ct1_score=result.ct_scores["CT1"],
        ct2_score=result.ct_scores["CT2"],
        ct3_score=result.ct_scores["CT3"],
        ct4_score=result.ct_scores["CT4"],
        ct5_score=result.ct_scores["CT5"],
        ct6_score=result.ct_scores["CT6"],
        ct7_score=result.ct_scores["CT7"],
        ct8_score=result.ct_scores["CT8"],
        ct_confidence=ct_confidence_str,
        overall_score=result.overall_score,
        overall_level=result.overall_level,
        weak_cts=",".join(result.weak_cts) if result.weak_cts else None,
        strong_cts=",".join(result.strong_cts) if result.strong_cts else None,
        update_time=datetime.now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.achievement_id  # type: ignore[return-value]


def refresh_ct_achievement(session: Session, course_id: int) -> dict:
    """刷新课程内所有学生的 CT 达成度（接入 analysis_refresh 主编排）。

    全程 try/except 降级，失败不阻断主刷新流程。
    """
    student_ids = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()
    updated = 0
    for sid in student_ids:
        try:
            persist_ct_achievement(session, sid, course_id)
            updated += 1
        except Exception:
            continue
    return {"students_processed": len(student_ids), "ct_achievements_updated": updated}
