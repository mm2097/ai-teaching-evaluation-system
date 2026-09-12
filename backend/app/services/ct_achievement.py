"""课程目标(CT1-CT8)达成度算法（证据项加权归因版）。

三级归因模型（按证据强度递减），每个 CT 收集带来源的证据项，前端可展示归因过程：
  1. 知识点精确归因（CT1-CT4，high）：学生各知识点掌握度 → 按 KnowledgePoint.course_objectives
     主/次归属加权分配到 CT（主归属权重 1.0、次归属 0.4），避免映射重叠导致 CT 趋同。
  2. 试卷大题归因（CT1-CT4，medium）：CourseTestDetail 大题知识点 → 知识点 → CT，得分率作为证据。
  3. 考核批次类型归因（CT1-CT6，medium）：按 ExamBatch.batch_type 查 BATCH_TYPE_CT_WEIGHTS 分配。
  4. 素养推断（CT7-CT8，low）：实践成绩 + 考勤 + 课堂参与 组合推断。

设计要点：
  - 每个 CT 维护 evidence 列表，最终 score = Σ(contribution) / Σ(weight)（加权平均）。
  - 无证据的 CT 标 None，不计入总体达成度（不强行赋 0 分）。
  - 计算全程 try/except 降级，失败不阻断 analysis_refresh 主流程。
  - 复用 mastery.compute_mastery_index_with_fallback，不重复造轮子。
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
    KP_CT_PRIMARY_WEIGHT,
    KP_CT_SECONDARY_WEIGHT,
    degree_to_level,
    parse_ct_field,
)
from app.services.mastery import compute_mastery_index_with_fallback

# 试卷每大题满分（5 大题 × 20 分 = 100 分，与 mastery.EXAM_QUESTION_FULL_SCORE 一致）
_EXAM_Q_FULL = 20.0


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class CTEvidence:
    """单条归因证据：某个数据源对某 CT 的贡献。"""
    source: str          # 来源名："期中考试"/"知识点:以太网帧格式"/"实验报告"/"考勤"
    source_type: str     # "exam"|"knowledge"|"batch"|"literacy"
    weight: float        # 该证据对 CT 的归因权重（>0）
    score: float         # 该证据的得分率（0-100）
    contribution: float  # weight * score（贡献分）

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "weight": round(self.weight, 2),
            "score": round(self.score, 1),
            "contribution": round(self.contribution, 1),
        }


@dataclass
class CTScore:
    """单个 CT 的达成度结果：分数 + 置信度 + 证据链。"""
    score: float | None = None
    confidence: str | None = None
    evidence: list[CTEvidence] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.score is not None


@dataclass
class CTAchievementResult:
    """单学生 CT 达成度计算结果（内存结构，落库前用）。"""
    student_id: int
    course_id: int
    ct: dict[str, CTScore] = field(default_factory=dict)  # CT1-CT8 -> CTScore

    def __post_init__(self):
        if not self.ct:
            self.ct = {ct: CTScore() for ct in CT_CODES}

    @property
    def ct_scores(self) -> dict[str, float | None]:
        return {ct: cs.score for ct, cs in self.ct.items()}

    @property
    def ct_confidence(self) -> dict[str, str]:
        return {ct: cs.confidence for ct, cs in self.ct.items() if cs.confidence}

    @property
    def weak_cts(self) -> list[str]:
        """达成度 < 60 的 CT 编号。"""
        return [ct for ct, cs in self.ct.items() if cs.score is not None and cs.score < 60]

    @property
    def strong_cts(self) -> list[str]:
        """达成度 ≥ 85 的 CT 编号。"""
        return [ct for ct, cs in self.ct.items() if cs.score is not None and cs.score >= 85]

    @property
    def overall_score(self) -> float:
        """总体达成度 = 有证据 CT 的均值。无证据返回 0.0。"""
        valid = [cs.score for cs in self.ct.values() if cs.score is not None]
        return round(sum(valid) / len(valid), 1) if valid else 0.0

    @property
    def overall_level(self) -> str:
        """总体达成等级。"""
        valid = [cs.score for cs in self.ct.values() if cs.score is not None]
        return degree_to_level(self.overall_score) if valid else "—"

    def _finalize(self) -> None:
        """对每个 CT 按 evidence 加权平均算出最终 score。无证据则保持 None。"""
        for cs in self.ct.values():
            if not cs.evidence:
                continue
            total_w = sum(e.weight for e in cs.evidence)
            if total_w <= 0:
                continue
            total_c = sum(e.contribution for e in cs.evidence)
            cs.score = round(total_c / total_w, 1)

    def to_dict(self) -> dict:
        """前端响应结构（含证据链）。"""
        overall = self.overall_score
        overall_level = self.overall_level
        return {
            "ct_scores": {
                ct: {
                    "score": cs.score,
                    "level": degree_to_level(cs.score) if cs.score is not None else None,
                    "confidence": cs.confidence,
                    "desc": CT_DEFINITIONS[ct]["desc"],
                    "category": CT_DEFINITIONS[ct]["category"],
                    "evidence": [e.to_dict() for e in cs.evidence],
                }
                for ct, cs in self.ct.items()
            },
            "overall": {"score": overall, "level": overall_level},
            "weak_cts": self.weak_cts,
            "strong_cts": self.strong_cts,
            "radar": {ct: cs.score for ct, cs in self.ct.items()},
        }


# ============================================================================
# 归因子函数
# ============================================================================

def _knowledge_ct_evidence(
    session: Session, student_id: int, course_id: int
) -> dict[str, list[CTEvidence]]:
    """知识点精确归因（CT1-CT4，high）。

    取学生各知识点掌握度，按 KnowledgePoint.course_objectives 主/次归属加权分配：
    course_objectives 第一个 CT 为主归属（权重 KP_CT_PRIMARY_WEIGHT），其余次归属（KP_CT_SECONDARY_WEIGHT）。
    返回 {CT: [evidence...]}，仅 CT1-CT4。
    """
    mastery_index = compute_mastery_index_with_fallback(
        session, course_id, [student_id]
    )
    out: dict[str, list[CTEvidence]] = {ct: [] for ct in CT_CODES[:4]}
    for kp in _course_points(session, course_id):
        score = mastery_index.get((student_id, kp.point_id))
        if score is None:
            continue
        cts = parse_ct_field(kp.course_objectives)
        if not cts:
            continue
        for idx, ct in enumerate(cts):
            if ct not in out:
                continue
            w = KP_CT_PRIMARY_WEIGHT if idx == 0 else KP_CT_SECONDARY_WEIGHT
            out[ct].append(CTEvidence(
                source=f"知识点:{kp.point_name}",
                source_type="knowledge",
                weight=w,
                score=score,
                contribution=w * score,
            ))
    return out


def _test_detail_ct_evidence(
    session: Session, student_id: int, course_id: int
) -> dict[str, list[CTEvidence]]:
    """试卷大题扣分归因（CT1-CT4，medium）。

    CourseTestDetail.questionN_knowledge（文本知识点名）→ 模糊匹配 KnowledgePoint → CT。
    得分率 = (满分 - 扣分) / 满分，按 CT 聚合为证据项。
    """
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

    # 批次名（用于证据来源标注）
    batch_id_name = {
        b.batch_id: b.batch_name for b in
        session.exec(select(ExamBatch).where(ExamBatch.batch_id.in_(batch_ids))).all()  # type: ignore[arg-type]
    }

    details = session.exec(
        select(CourseTestDetail).where(
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
            CourseTestDetail.student_id == student_id,
        )
    ).all()

    # 按 (来源批次, CT) 聚合得分率，最终一条证据代表"该试卷对该 CT 的贡献"
    agg: dict[tuple[str, str], list[float]] = {}
    for d in details:
        batch_label = batch_id_name.get(d.exam_batch_id, "试卷")
        for qn in range(1, 6):
            try:
                deduction = float(getattr(d, f"question{qn}_score") or 0)
            except (TypeError, ValueError):
                deduction = 0.0
            knowledge_text = getattr(d, f"question{qn}_knowledge") or ""
            if not knowledge_text:
                continue
            names = _split_knowledge_names(knowledge_text)
            cts_found: list[str] = []
            for name in names:
                if name in name_to_cts:
                    cts_found.extend(name_to_cts[name])
            if not cts_found:
                continue
            rate = max(0.0, (_EXAM_Q_FULL - deduction) / _EXAM_Q_FULL) * 100
            for ct in set(cts_found) & set(CT_CODES[:4]):
                agg.setdefault((batch_label, ct), []).append(rate)

    out: dict[str, list[CTEvidence]] = {ct: [] for ct in CT_CODES[:4]}
    for (batch_label, ct), rates in agg.items():
        avg_rate = round(sum(rates) / len(rates), 1)
        # 试卷大题是高价值证据，权重与知识点主归属持平
        out[ct].append(CTEvidence(
            source=f"{batch_label}·大题",
            source_type="exam",
            weight=KP_CT_PRIMARY_WEIGHT,
            score=avg_rate,
            contribution=KP_CT_PRIMARY_WEIGHT * avg_rate,
        ))
    return out


def _batch_ct_evidence(
    session: Session, student_id: int, course_id: int
) -> dict[str, list[CTEvidence]]:
    """考核批次类型归因（CT1-CT6，medium）。

    各批次成绩得分率 × BATCH_TYPE_CT_WEIGHTS 中该 batch_type 的 CT 权重，
    作为证据项（权重=该批次类型对该 CT 的归因权重）。
    """
    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id)
    ).all()
    if not batches:
        return {}

    batch_ids = [b.batch_id for b in batches]
    batch_type_map = {b.batch_id: b.batch_type for b in batches}
    batch_name_map = {b.batch_id: b.batch_name for b in batches}
    full_score = 100.0

    score_map: dict[int, float] = {}
    for bid, sc in session.exec(
        select(ScoreRecord.batch_id, ScoreRecord.score).where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all():
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))
    for bid, sc in session.exec(
        select(IndividualScore.exam_batch_id, IndividualScore.score).where(
            IndividualScore.student_id == student_id,
            IndividualScore.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all():
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))
    for bid, sc in session.exec(
        select(CourseTestDetail.exam_batch_id, CourseTestDetail.total_score).where(
            CourseTestDetail.student_id == student_id,
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
        )
    ).all():
        score_map[bid] = max(score_map.get(bid, 0.0), float(sc))

    out: dict[str, list[CTEvidence]] = {ct: [] for ct in CT_CODES}
    for bid, score in score_map.items():
        btype = batch_type_map.get(bid)
        if btype is None:
            continue
        weights = BATCH_TYPE_CT_WEIGHTS.get(btype)
        if not weights:
            continue
        rate = max(0.0, min(100.0, score / full_score * 100))
        bname = batch_name_map.get(bid, f"批次{bid}")
        for ct, w in weights.items():
            if w <= 0:
                continue
            out.setdefault(ct, []).append(CTEvidence(
                source=bname,
                source_type="batch",
                weight=w,
                score=rate,
                contribution=w * rate,
            ))
    return out


def _literacy_ct_evidence(
    session: Session, student_id: int, course_id: int
) -> dict[str, list[CTEvidence]]:
    """素养类推断（CT7-CT8，low）。

    CT7 ≈ 0.5×实践成绩得分率 + 0.3×考勤率 + 0.2×课堂参与率
    CT8 ≈ 0.6×实践成绩得分率 + 0.4×课堂参与率
    每项作为独立证据，让前端能看到素养分由哪些维度拼成。
    """
    practice = _practice_score_rate(session, student_id, course_id)
    attendance = _attendance_rate(session, student_id, course_id)
    participation = _participation_rate(session, student_id, course_id)

    def _ev(src: str, w: float, sc: float) -> CTEvidence:
        return CTEvidence(source=src, source_type="literacy", weight=w, score=sc, contribution=w * sc)

    ct7: list[CTEvidence] = [
        _ev("实践成绩", CT7_LITERACY_WEIGHTS["practice"], practice),
        _ev("考勤", CT7_LITERACY_WEIGHTS["attendance"], attendance),
        _ev("课堂参与", CT7_LITERACY_WEIGHTS["participation"], participation),
    ]
    ct8: list[CTEvidence] = [
        _ev("实践成绩", CT8_LITERACY_WEIGHTS["practice"], practice),
        _ev("课堂参与", CT8_LITERACY_WEIGHTS["participation"], participation),
    ]
    return {"CT7": ct7, "CT8": ct8}


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
    """单学生 CT1-CT8 达成度（核心算法，证据项加权归因版）。

    归因顺序（逐层追加证据，最终加权平均）：
      CT1-CT4：知识点精确归因（high）+ 试卷大题归因（medium）+ 批次类型补充
      CT4-CT6：批次类型归因（medium）
      CT7-CT8：素养推断（low）
    同一 CT 的多条证据按 weight 加权平均得到最终分数。
    """
    result = CTAchievementResult(student_id=student_id, course_id=course_id)

    def _merge(ev_map: dict[str, list[CTEvidence]], confidence: str | None = None) -> None:
        """把某归因层的证据追加到 result，并标记置信度（仅当该 CT 首次有证据时设 confidence）。"""
        for ct, evs in ev_map.items():
            if ct not in result.ct:
                continue
            if evs:
                result.ct[ct].evidence.extend(evs)
                if result.ct[ct].confidence is None and confidence:
                    result.ct[ct].confidence = confidence

    # 1. 知识点精确归因（CT1-CT4，high）
    _merge(_knowledge_ct_evidence(session, student_id, course_id), "high")

    # 2. 试卷大题归因（CT1-CT4，medium）
    _merge(_test_detail_ct_evidence(session, student_id, course_id), "medium")

    # 3. 考核批次类型归因（CT1-CT6，medium）
    _merge(_batch_ct_evidence(session, student_id, course_id), "medium")

    # 4. 素养推断（CT7-CT8，low）—— 素养类直接覆盖（其证据结构独立）
    lit = _literacy_ct_evidence(session, student_id, course_id)
    for ct, evs in lit.items():
        if ct in result.ct and evs:
            result.ct[ct].evidence = evs  # 素养类用独立证据集
            result.ct[ct].confidence = "low"

    result._finalize()
    return result


def compute_class_ct(
    session: Session, course_id: int, class_id: int | None = None
) -> dict:
    """班级 CT 达成度总览。

    返回 {ct_avg, ct_std, ct_pass_rate, weak_cts_class, ct_evidence_summary, students}。
    students 每人精简（ct_scores + overall，不带 evidence，避免响应过大）。
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

    # 各 CT 全班均值 / 标准差 / 达成率 / 分档分布
    ct_avg: dict[str, float] = {}
    ct_std: dict[str, float] = {}
    ct_pass_rate: dict[str, float] = {}
    ct_level_dist: dict[str, dict[str, float]] = {}
    ct_evidence_summary: dict[str, list[dict]] = {}
    for ct in CT_CODES:
        vals = [r.ct[ct].score for _, r in per_student if r.ct[ct].score is not None]
        if vals:
            n = len(vals)
            ct_avg[ct] = round(sum(vals) / n, 1)
            mean = ct_avg[ct]
            ct_std[ct] = round(math.sqrt(sum((v - mean) ** 2 for v in vals) / n), 1)
            # 达成率 = 达到合格线(≥60)的比例
            ct_pass_rate[ct] = round(sum(1 for v in vals if v >= 60) / n, 3)
            # 分档分布：优秀≥85 / 良好70-84 / 合格60-69 / 未达成<60
            exc = sum(1 for v in vals if v >= 85)
            good = sum(1 for v in vals if 70 <= v < 85)
            pas = sum(1 for v in vals if 60 <= v < 70)
            fail = n - exc - good - pas
            ct_level_dist[ct] = {
                "excellent": round(exc / n, 3),
                "good": round(good / n, 3),
                "pass": round(pas / n, 3),
                "fail": round(fail / n, 3),
            }
        else:
            ct_avg[ct] = 0.0
            ct_std[ct] = 0.0
            ct_pass_rate[ct] = 0.0
            ct_level_dist[ct] = {"excellent": 0.0, "good": 0.0, "pass": 0.0, "fail": 0.0}

        # 班级证据来源汇总：取所有学生该 CT 的证据，按 source 聚合平均得分率与平均权重
        src_agg: dict[str, list[tuple[float, float]]] = {}  # source -> [(weight, score)]
        for _, r in per_student:
            for ev in r.ct[ct].evidence:
                src_agg.setdefault(ev.source, []).append((ev.weight, ev.score))
        summary = []
        for src, pairs in src_agg.items():
            n = len(pairs)
            avg_w = sum(w for w, _ in pairs) / n
            avg_s = sum(s for _, s in pairs) / n
            summary.append({"source": src, "avg_weight": round(avg_w, 2), "avg_score": round(avg_s, 1), "count": n})
        # 按平均贡献（权重×得分率）降序，取前 4 条作为该 CT 的主要证据
        summary.sort(key=lambda x: x["avg_weight"] * x["avg_score"], reverse=True)
        ct_evidence_summary[ct] = summary[:4]

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
        "ct_level_dist": ct_level_dist,
        "weak_cts_class": weak_cts_class,
        "ct_evidence_summary": ct_evidence_summary,
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

    scores = result.ct_scores
    valid = [s for s in scores.values() if s is not None]
    if not valid:
        return 0

    conf = result.ct_confidence
    conf_parts = [conf.get(ct) or "" for ct in CT_CODES]
    ct_confidence_str = ",".join(conf_parts) if any(conf_parts) else None

    overall = round(sum(valid) / len(valid), 1)
    overall_level = degree_to_level(overall)

    row = CTAchievement(
        course_id=course_id,
        student_id=student_id,
        ct1_score=scores["CT1"],
        ct2_score=scores["CT2"],
        ct3_score=scores["CT3"],
        ct4_score=scores["CT4"],
        ct5_score=scores["CT5"],
        ct6_score=scores["CT6"],
        ct7_score=scores["CT7"],
        ct8_score=scores["CT8"],
        ct_confidence=ct_confidence_str,
        overall_score=overall,
        overall_level=overall_level,
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
