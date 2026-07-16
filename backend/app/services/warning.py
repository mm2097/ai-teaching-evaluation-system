"""D06/D07 异常学情预警规则引擎。

5 条规则（阈值可配置，见 WARNING_CONFIG）：
    W1  成绩下滑      相邻两次考核下降 ≥ 15 分
    W2  成绩暴跌      单次低于班级均值 2σ
    W3  缺勤超标      缺勤 ≥ 3 次（或缺勤率 > 20%）
    W4  作业未提交    累计未提交 ≥ 2 次
    W5  知识点薄弱堆积 薄弱（<60%）≥ 3 个

等级判定（D07）：
    高  命中 W2 或 同时命中 ≥ 3 条
    中  命中 2 条，或 单条 W1 下滑 ≥ 25 分
    低  其他单条命中
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import (
    AttendanceRecord,
    AttendanceSheet,
    CourseStudent,
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    InteractionRecord,
    ScoreRecord,
    StudyWarning,
    Student,
)
from app.services.predict import get_student_slope

# 默认阈值（可外部覆盖）
WARNING_CONFIG = {
    "w1_drop": 15.0,         # 相邻两次下降 ≥ 15
    "w1_severe_drop": 25.0,  # 严重下滑 ≥ 25（升级用）
    "w2_sigma": 2.0,         # 2σ 离群
    "w3_absence_count": 3,   # 缺勤 ≥ 3 次
    "w3_absence_rate": 0.2,  # 或缺勤率 > 20%
    "w4_miss_hw": 2,         # 未提交 ≥ 2 次
    "w5_weak_count": 3,      # 薄弱知识点 ≥ 3
    "weak_threshold": 60.0,
}


@dataclass
class WarningHit:
    rule: str            # W1..W5
    level: str           # 高 / 中 / 低
    reason: str


@dataclass
class WarningResult:
    student_id: int
    hits: list[WarningHit] = field(default_factory=list)
    final_level: str = "无"   # 高/中/低/无
    level_code: int = 0       # 3/2/1/0

    def add(self, hit: WarningHit) -> None:
        self.hits.append(hit)


def _check_w1_w2_scores(
    session: Session, student_id: int, course_id: int
) -> list[WarningHit]:
    """W1 成绩下滑 + W2 暴跌离群。"""
    hits: list[WarningHit] = []

    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
        .order_by(ExamBatch.create_time)
    ).all()
    if len(batch_ids) < 2:
        return hits

    # Collect score entries across all three tables
    score_entries: list[tuple[int, str, float, int]] = []
    # (batch_id, batch_name, score, source_type: 1=ScoreRecord, 2=IndividualScore, 3=CourseTestDetail)

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
        score_entries.append((eb.batch_id, eb.batch_name, float(sr.score), 1))

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
        score_entries.append((eb.batch_id, eb.batch_name, float(isc.score), 2))

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
        score_entries.append((eb.batch_id, eb.batch_name, float(ctd.total_score), 3))

    # Sort by batch creation order
    bid_order = {bid: i for i, bid in enumerate(batch_ids)}
    score_entries.sort(key=lambda x: bid_order.get(x[0], 999))

    if len(score_entries) < 2:
        return hits

    # W1：相邻下降
    cfg_drop = WARNING_CONFIG["w1_drop"]
    cfg_severe = WARNING_CONFIG["w1_severe_drop"]
    for i in range(1, len(score_entries)):
        prev = score_entries[i - 1][2]
        curr = score_entries[i][2]
        drop = prev - curr
        if drop >= cfg_severe:
            hits.append(WarningHit(
                rule="W1", level="中",
                reason=f"{score_entries[i][1]}较上次下滑 {drop:.1f} 分（严重）"
            ))
        elif drop >= cfg_drop:
            hits.append(WarningHit(
                rule="W1", level="低",
                reason=f"{score_entries[i][1]}较上次下滑 {drop:.1f} 分"
            ))

    # W2：单次低于班级均值 2σ
    cfg_sigma = WARNING_CONFIG["w2_sigma"]
    for bid, bname, sscore, stype in score_entries:
        if stype == 1:  # ScoreRecord
            class_scores = session.exec(
                select(ScoreRecord.score).where(ScoreRecord.batch_id == bid)
            ).all()
        elif stype == 2:  # IndividualScore
            class_scores = session.exec(
                select(IndividualScore.score).where(IndividualScore.exam_batch_id == bid)
            ).all()
        else:  # CourseTestDetail
            class_scores = session.exec(
                select(CourseTestDetail.total_score).where(CourseTestDetail.exam_batch_id == bid)
            ).all()
        if len(class_scores) < 3:
            continue
        mean = sum(class_scores) / len(class_scores)
        var = sum((s - mean) ** 2 for s in class_scores) / len(class_scores)
        std = math.sqrt(var) or 1.0
        if (mean - sscore) > cfg_sigma * std:
            hits.append(WarningHit(
                rule="W2", level="高",
                reason=f"{bname}成绩低于班级均值 {cfg_sigma}σ（统计离群）"
            ))
    return hits


def _check_w3_attendance(
    session: Session, student_id: int, course_id: int
) -> list[WarningHit]:
    """W3 缺勤超标。"""

    _ATTENDANCE_SLOTS = [
        "attendance_1", "attendance_2", "attendance_3", "attendance_4",
        "attendance_5", "attendance_6", "attendance_7", "attendance_8",
        "attendance_9", "attendance_10", "attendance_11", "attendance_12",
        "attendance_13", "attendance_14", "attendance_15", "attendance_16",
        "attendance_17", "attendance_18", "attendance_19", "attendance_20",
        "attendance_21", "attendance_22", "attendance_23", "attendance_24",
        "attendance_25", "attendance_26", "attendance_27", "attendance_28",
        "attendance_29", "attendance_30", "attendance_31", "attendance_32",
    ]

    attendance_batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()

    # AttendanceRecord（旧表兼容）
    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.course_id == course_id,
        )
    ).all()
    absent_old = sum(1 for r in records if r.status == 3)

    # AttendanceSheet（新表）
    sheets = session.exec(
        select(AttendanceSheet).where(
            AttendanceSheet.student_id == student_id,
            AttendanceSheet.exam_batch_id.in_(attendance_batch_ids),  # type: ignore
        )
    ).all()

    absent_new = 0
    att_sheet_slots = 0
    for sh in sheets:
        for attr in _ATTENDANCE_SLOTS:
            val = getattr(sh, attr, None)
            if val is not None:
                att_sheet_slots += 1
                if "缺" in str(val):
                    absent_new += 1

    absent = absent_old + absent_new
    att_total = len(records) + att_sheet_slots

    if not records and not sheets:
        return []

    rate = absent / max(att_total, 1)
    if absent >= WARNING_CONFIG["w3_absence_count"] or rate > WARNING_CONFIG["w3_absence_rate"]:
        return [WarningHit(
            rule="W3", level="低",
            reason=f"累计缺勤 {absent} 次（缺勤率 {rate*100:.0f}%）"
        )]
    return []


def _check_w4_homework(
    session: Session, student_id: int, course_id: int
) -> list[WarningHit]:
    """W4 作业未提交（已禁用）。"""
    return []  # disabled


def _check_w5_mastery(
    session: Session, student_id: int, course_id: int, weak_count: int
) -> list[WarningHit]:
    """W5 知识点薄弱堆积（薄弱数由调用方传入）。"""
    if weak_count >= WARNING_CONFIG["w5_weak_count"]:
        return [WarningHit(
            rule="W5", level="低",
            reason=f"薄弱知识点 {weak_count} 个"
        )]
    return []


def _resolve_level(hits: list[WarningHit]) -> tuple[str, int]:
    """D07 等级判定。"""
    if not hits:
        return "无", 0
    # 命中 W2 直接高
    if any(h.rule == "W2" for h in hits):
        return "高", 3
    if len(hits) >= 3:
        return "高", 3
    if len(hits) == 2:
        return "中", 2
    # 单条：中已在 W1 严重下滑时设置；其余为低
    levels = [h.level for h in hits]
    if "中" in levels:
        return "中", 2
    return "低", 1


def evaluate_student(
    session: Session, student_id: int, course_id: int, weak_count: int = 0
) -> WarningResult:
    """对单个学生执行全部规则评估。"""
    result = WarningResult(student_id=student_id)
    for h in _check_w1_w2_scores(session, student_id, course_id):
        result.add(h)
    for h in _check_w3_attendance(session, student_id, course_id):
        result.add(h)
    for h in _check_w4_homework(session, student_id, course_id):
        result.add(h)
    for h in _check_w5_mastery(session, student_id, course_id, weak_count):
        result.add(h)

    level, code = _resolve_level(result.hits)
    result.final_level = level
    result.level_code = code
    return result


def scan_course_warnings(
    session: Session, course_id: int, class_id: int | None = None
) -> list[WarningResult]:
    """扫描课程/班级所有学生，返回命中预警的学生列表。"""
    from app.services.mastery import compute_student_mastery

    stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    if class_id:
        in_class = session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all()
        stmt = stmt.where(CourseStudent.student_id.in_(in_class))  # type: ignore
    student_ids = session.exec(stmt).all()

    out: list[WarningResult] = []
    for sid in student_ids:
        # 计算薄弱数
        weak_count = 0
        for m in compute_student_mastery(session, sid, course_id):
            if m.accuracy < WARNING_CONFIG["weak_threshold"]:
                weak_count += 1
        r = evaluate_student(session, sid, course_id, weak_count)
        if r.hits:
            out.append(r)
    return out


def persist_warnings(session: Session, results: list[WarningResult], course_id: int) -> int:
    """把扫描结果落库（去重：同一学生同一规则只保留最新一条）。返回写入条数。"""
    # 先清掉本课程未处理的旧预警（避免重复堆积）
    old = session.exec(
        select(StudyWarning).where(
            StudyWarning.course_id == course_id,
            StudyWarning.handle_status == 0,
        )
    ).all()
    for o in old:
        session.delete(o)

    count = 0
    for r in results:
        for h in r.hits:
            session.add(StudyWarning(
                course_id=course_id,
                student_id=r.student_id,
                warning_type=f"{h.rule}:{h.reason[:30]}",
                warning_level=r.level_code,
                warning_reason=h.reason,
                handle_status=0,
            ))
            count += 1
    session.commit()
    return count
