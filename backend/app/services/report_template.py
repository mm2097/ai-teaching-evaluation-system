"""D10 报告结论与建议 - 模板兜底（必走）。

LLM 增强在 algorithm/src/reporter.py，失败回退此模块输出。
两种报告：班级报告 / 学生个人报告。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    AttendanceRecord,
    AttendanceSheet,
    ClassInfo,
    Course,
    CourseStudent,
    CourseTestDetail,
    ExamBatch,
    IndividualScore,
    ScoreRecord,
    Student,
)
from app.services.evaluation import (
    class_eval_snapshot,
    load_course_eval_scheme,
    score_eval_scheme_for_student,
)
from app.services.mastery import compute_class_mastery, compute_student_mastery
from app.services.profile import compute_profile
from app.services.tag import generate_tags
from app.services.warning import evaluate_student, scan_course_warnings


@dataclass
class ReportContext:
    """报告生成所需上下文（模板与 LLM 通用）。"""

    scope: str = "class"           # class / student
    report_type: int = 1           # 1=班级学情 2=学生个人 3=课程知识点 4=学习质量
    course_id: int = 0
    course_name: str = ""
    student_id: Optional[int] = None
    student_name: str = ""
    class_name: str = ""

    avg_score: float = 0.0
    pass_rate: float = 0.0
    excellent_rate: float = 0.0
    weak_points: list[str] = field(default_factory=list)
    strong_points: list[str] = field(default_factory=list)
    trend: str = "稳定"
    risk_count: int = 0

    # 学生专属
    tags: list[str] = field(default_factory=list)
    radar: dict = field(default_factory=dict)

    # 可视化快照（报告预览 / Excel 图表）
    knowledge_mastery: list[dict] = field(default_factory=list)
    score_buckets: list[dict] = field(default_factory=list)

    # 更细的现状指标
    student_count: int = 0
    attendance_rate: float = 0.0
    latest_exam_name: str = ""
    score_min: float = 0.0
    score_max: float = 0.0
    score_median: float = 0.0
    warnings: list[dict] = field(default_factory=list)
    evaluation: dict = field(default_factory=dict)
    score_history: list[dict] = field(default_factory=list)
    predicted_score: float = 0.0
    confidence: float = 0.0
    findings: list[str] = field(default_factory=list)
    eval_snapshot: dict = field(default_factory=dict)
    exam_batches: list[dict] = field(default_factory=list)


def _build_score_buckets(scores: list[float]) -> list[dict]:
    """按五档成绩段统计人数，供饼图/柱状图使用。"""
    labels = ["不及格 (<60)", "及格 (60-69)", "中等 (70-79)", "良好 (80-89)", "优秀 (≥90)"]
    counts = [0, 0, 0, 0, 0]
    for score in scores:
        if score < 60:
            counts[0] += 1
        elif score < 70:
            counts[1] += 1
        elif score < 80:
            counts[2] += 1
        elif score < 90:
            counts[3] += 1
        else:
            counts[4] += 1
    total = len(scores) or 1
    return [
        {"label": label, "count": count, "ratio": round(count / total * 100, 1)}
        for label, count in zip(labels, counts)
    ]


def _median(scores: list[float]) -> float:
    ordered = sorted(scores)
    size = len(ordered)
    if not size:
        return 0.0
    mid = size // 2
    if size % 2:
        return round(ordered[mid], 1)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def _mastery_to_chart(masteries) -> list[dict]:
    items = [
        {
            "name": m.point_name,
            "accuracy": m.accuracy,
            "level": m.level,
            "module": getattr(m, "module_name", "") or "",
        }
        for m in masteries
    ]
    return sorted(items, key=lambda item: item["accuracy"])


def _class_attendance_rate(session: Session, course_id: int, student_ids: list[int]) -> float:
    """班级平均出勤率（到课人次 / 应到人次），无考勤数据时返回 0。"""
    if not student_ids:
        return 0.0
    sid_set = set(student_ids)
    totals: dict[int, int] = defaultdict(int)
    presents: dict[int, int] = defaultdict(int)

    records = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.course_id == course_id,
            AttendanceRecord.student_id.in_(student_ids),  # type: ignore
        )
    ).all()
    for record in records:
        totals[record.student_id] += 1
        if record.status == 0:
            presents[record.student_id] += 1

    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    if batch_ids:
        sheets = session.exec(
            select(AttendanceSheet).where(AttendanceSheet.exam_batch_id.in_(batch_ids))  # type: ignore
        ).all()
        for sheet in sheets:
            if sheet.student_id not in sid_set:
                continue
            if sheet.total_count:
                totals[sheet.student_id] += int(sheet.total_count)
                presents[sheet.student_id] += int(sheet.present_count or 0)

    rates = [
        presents[sid] / totals[sid]
        for sid in student_ids
        if totals.get(sid)
    ]
    if not rates:
        return 0.0
    return round(sum(rates) / len(rates) * 100, 1)


def _warning_rows(session: Session, course_id: int, class_id: int | None, student_ids: list[int]) -> list[dict]:
    results = scan_course_warnings(session, course_id, class_id)
    if not results:
        return []
    name_map = {
        student.student_id: student.real_name
        for student in session.exec(
            select(Student).where(Student.student_id.in_(student_ids))  # type: ignore
        ).all()
    }
    level_rank = {"高": 0, "中": 1, "低": 2}
    rows = [
        {
            "student_id": item.student_id,
            "name": name_map.get(item.student_id, str(item.student_id)),
            "level": item.final_level,
            "reasons": [hit.reason for hit in item.hits],
        }
        for item in results
    ]
    rows.sort(key=lambda row: (level_rank.get(row["level"], 9), row["name"]))
    return rows


def _fmt_knowledge(items: list[dict], limit: int = 5) -> str:
    if not items:
        return "暂无"
    return "、".join(f"{item['name']}（{item['accuracy']}%）" for item in items[:limit])


def _fmt_buckets(buckets: list[dict]) -> str:
    parts = [
        f"{item['label']} {item['count']} 人（{item.get('ratio', 0)}%）"
        for item in buckets
        if item.get("count")
    ]
    return "，".join(parts) if parts else "暂无分布数据"


def _level_by_score(score: float) -> str:
    if score >= 85:
        return "良好"
    if score >= 75:
        return "中等偏上"
    if score >= 60:
        return "一般"
    return "偏低"


def _metrics_from_ctx(ctx: ReportContext) -> dict:
    return {
        "studentCount": ctx.student_count,
        "avgScore": ctx.avg_score,
        "passRate": ctx.pass_rate,
        "excellentRate": ctx.excellent_rate,
        "attendanceRate": ctx.attendance_rate,
        "warningCount": ctx.risk_count,
        "scoreMin": ctx.score_min,
        "scoreMax": ctx.score_max,
        "scoreMedian": ctx.score_median,
        "latestExam": ctx.latest_exam_name,
        "predictedScore": ctx.predicted_score,
        "evalLevel": ctx.evaluation.get("level", ""),
        "evalScore": ctx.evaluation.get("total", ""),
    }


def _collect_scores_for_batch(session: Session, batch_id: int | None, student_ids: list[int]) -> list[float]:
    if not batch_id or not student_ids:
        return []
    scores: list[float] = []
    scores.extend(float(value) for value in session.exec(
        select(ScoreRecord.score).where(
            ScoreRecord.batch_id == batch_id,
            ScoreRecord.student_id.in_(student_ids),  # type: ignore
        )
    ).all())
    scores.extend(float(value) for value in session.exec(
        select(IndividualScore.score).where(
            IndividualScore.exam_batch_id == batch_id,
            IndividualScore.student_id.in_(student_ids),  # type: ignore
        )
    ).all())
    scores.extend(float(value) for value in session.exec(
        select(CourseTestDetail.total_score).where(
            CourseTestDetail.exam_batch_id == batch_id,
            CourseTestDetail.student_id.in_(student_ids),  # type: ignore
        )
    ).all())
    return scores


def _class_exam_history(session: Session, course_id: int, student_ids: list[int]) -> list[dict]:
    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id).order_by(ExamBatch.create_time)
    ).all()
    history = []
    for batch in batches:
        scores = _collect_scores_for_batch(session, batch.batch_id, student_ids)
        if not scores:
            continue
        history.append({
            "name": batch.batch_name,
            "score": round(sum(scores) / len(scores), 1),
            "weight": batch.batch_weight,
            "count": len(scores),
        })
    return history


def _fmt_scheme(scheme: list[dict], with_score: bool = True) -> str:
    if not scheme:
        return "本课程尚未配置评价维度，暂按系统默认口径。"
    parts = []
    for dim in scheme:
        indexes = dim.get("indexes") or []
        index_text = "、".join(
            f"{item['name']}{item.get('weight', 0):g}%"
            + (f"（{item['score']}分）" if with_score and item.get("score") is not None else "")
            for item in indexes
        )
        score_bit = f"均分 {dim['score']} 分，" if with_score and dim.get("score") is not None else ""
        parts.append(f"「{dim['name']}」{score_bit}含 {index_text or '未设指标'}")
    return "；".join(parts)


def _fmt_parts(parts: list[dict]) -> str:
    bits = [
        f"{item['name']}（权重{item.get('weight', 0):g}%）"
        + (f"{item['score']}分" if item.get("score") is not None else "暂无数据")
        for item in parts
    ]
    return "，".join(bits) if bits else "暂无学业构成数据"


def _apply_eval_snapshot(ctx: ReportContext, snapshot: dict) -> None:
    ctx.eval_snapshot = snapshot or {}
    if snapshot.get("radar"):
        ctx.radar = snapshot["radar"]
    if snapshot.get("total") is not None:
        ctx.evaluation = {
            "total": snapshot.get("total"),
            "level": snapshot.get("level"),
            "dimensions": snapshot.get("radar") or {},
            "scheme": snapshot.get("scheme") or [],
        }


def _fill_score_stats(ctx: ReportContext, scores: list[float], exam_name: str = "") -> None:
    if exam_name:
        ctx.latest_exam_name = exam_name
    if not scores:
        return
    ctx.avg_score = round(sum(scores) / len(scores), 1)
    ctx.pass_rate = round(sum(1 for score in scores if score >= 60) / len(scores) * 100, 1)
    ctx.excellent_rate = round(sum(1 for score in scores if score >= 85) / len(scores) * 100, 1)
    ctx.score_min = round(min(scores), 1)
    ctx.score_max = round(max(scores), 1)
    ctx.score_median = _median(scores)
    ctx.score_buckets = _build_score_buckets(scores)


def build_class_context(
    session: Session, course_id: int, class_id: Optional[int] = None,
    report_type: int = 1,
) -> ReportContext:
    """构建班级报告上下文。"""
    course = session.get(Course, course_id)
    class_info = session.get(ClassInfo, class_id) if class_id else None
    ctx = ReportContext(
        scope="class",
        report_type=report_type,
        course_id=course_id,
        course_name=course.course_name if course else "",
        class_name=class_info.class_name if class_info else "",
    )

    # 学生范围
    stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    if class_id:
        in_class = session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all()
        stmt = stmt.where(CourseStudent.student_id.in_(in_class))  # type: ignore
    sids = list(session.exec(stmt).all())
    ctx.student_count = len(sids)
    if not sids:
        return ctx

    ctx.attendance_rate = _class_attendance_rate(session, course_id, sids)
    ctx.eval_snapshot = {"scheme": load_course_eval_scheme(session, course_id), "radar": {}, "academicParts": []}

    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id).order_by(ExamBatch.create_time)
    ).all()
    ctx.exam_batches = [
        {"name": batch.batch_name, "weight": batch.batch_weight, "type": batch.batch_type}
        for batch in batches
    ]
    ctx.score_history = _class_exam_history(session, course_id, sids)
    if batches:
        last = batches[-1]
        _fill_score_stats(ctx, _collect_scores_for_batch(session, last.batch_id, sids), last.batch_name or "")

    class_mastery = compute_class_mastery(session, course_id, class_id)
    ctx.knowledge_mastery = _mastery_to_chart(class_mastery)
    ctx.weak_points = [m.point_name for m in class_mastery if m.accuracy < 60]
    ctx.strong_points = [m.point_name for m in class_mastery if m.accuracy >= 80]
    if report_type != 3:
        ctx.warnings = _warning_rows(session, course_id, class_id, sids)
        ctx.risk_count = len(ctx.warnings)
    if report_type in (1, 4):
        snapshot = class_eval_snapshot(session, course_id, sids, ctx.eval_snapshot.get("scheme"))
        _apply_eval_snapshot(ctx, snapshot)
    return ctx


def build_student_context(
    session: Session, student_id: int, course_id: int, report_type: int = 2,
) -> ReportContext:
    """构建学生报告上下文。"""
    course = session.get(Course, course_id)
    student = session.get(Student, student_id)
    cls = session.get(ClassInfo, student.class_id) if student else None

    ctx = ReportContext(
        scope="student",
        report_type=report_type,
        course_id=course_id,
        course_name=course.course_name if course else "",
        student_id=student_id,
        student_name=student.real_name if student else "",
        class_name=cls.class_name if cls else "",
        student_count=1,
    )

    profile = compute_profile(session, student_id, course_id)
    snapshot = score_eval_scheme_for_student(session, student_id, course_id, profile=profile)
    _apply_eval_snapshot(ctx, snapshot)
    ctx.attendance_rate = round(profile.attendance_rate * 100, 1)
    ctx.avg_score = profile.academic_score

    masteries = compute_student_mastery(session, student_id, course_id)
    ctx.knowledge_mastery = _mastery_to_chart(masteries)
    ctx.weak_points = [m.point_name for m in masteries if m.accuracy < 60]
    ctx.strong_points = [m.point_name for m in masteries if m.accuracy >= 80]

    ctx.tags = generate_tags(session, student_id, course_id)

    from app.services.predict import predict_student_scores
    pred = predict_student_scores(session, student_id, course_id)
    ctx.trend = pred.get("trend", "稳定")
    if pred.get("current"):
        ctx.avg_score = pred.get("current", ctx.avg_score)
    predicted = pred.get("predicted_mid", pred.get("predicted"))
    if isinstance(predicted, (int, float)):
        ctx.predicted_score = round(float(predicted), 1)
    ctx.confidence = float(pred.get("confidence") or 0)
    ctx.score_history = pred.get("history") or []
    history_scores = [float(item.get("score", 0)) for item in ctx.score_history if item.get("score") is not None]
    if history_scores:
        last_name = ctx.score_history[-1].get("name", "") if ctx.score_history else ""
        _fill_score_stats(ctx, history_scores, last_name)
        ctx.avg_score = pred.get("current") or ctx.avg_score

    warning = evaluate_student(session, student_id, course_id, len(ctx.weak_points))
    if warning.hits:
        ctx.warnings = [{
            "student_id": student_id,
            "name": ctx.student_name,
            "level": warning.final_level,
            "reasons": [hit.reason for hit in warning.hits],
        }]
        ctx.risk_count = 1
    return ctx


# ===== 模板兜底文本生成 =====

def _pack_report(ctx: ReportContext, summary: str, conclusion: str, suggestion: str, extra: dict | None = None) -> dict:
    snapshot = ctx.eval_snapshot or {}
    payload = {
        "scope": ctx.scope,
        "summary": summary,
        "conclusion": conclusion,
        "suggestion": suggestion,
        "source": "template",
        "findings": ctx.findings,
        "metrics": _metrics_from_ctx(ctx),
        "warnings": ctx.warnings if ctx.report_type != 3 else [],
        "evalScheme": snapshot.get("scheme") or [],
        "academicParts": snapshot.get("academicParts") or [],
        "levelDist": snapshot.get("levelDist") or {},
    }
    if extra:
        payload.update(extra)
    return payload


def render_class_report(ctx: ReportContext) -> dict:
    """班级学情：成绩结构、历次考核、出勤与预警，知识点只作附带。"""
    exam = ctx.latest_exam_name or "最近一次考核"
    scope = f"《{ctx.course_name}》" + (f"{ctx.class_name}" if ctx.class_name else "本教学班")
    level = _level_by_score(ctx.avg_score)
    fail_count = next((item["count"] for item in ctx.score_buckets if item["label"].startswith("不及格")), 0)
    high_warnings = [row for row in ctx.warnings if row.get("level") == "高"]
    history_text = " → ".join(f"{item['name']} {item['score']}分" for item in ctx.score_history[-5:]) or "暂无历次班级均分"
    scheme = (ctx.eval_snapshot or {}).get("scheme") or []
    weak_items = [item for item in ctx.knowledge_mastery if item["accuracy"] < 60]

    ctx.findings = [
        f"【班级学情】{scope}共 {ctx.student_count} 人。最近考核「{exam}」均分 {ctx.avg_score}，中位数 {ctx.score_median}，区间 {ctx.score_min}–{ctx.score_max}。",
        f"及格率 {ctx.pass_rate}%，优秀率 {ctx.excellent_rate}%，整体{level}。分档：{_fmt_buckets(ctx.score_buckets)}。",
        f"各次考核班级均分：{history_text}。",
        f"出勤率 {ctx.attendance_rate}%。" + (
            f"预警 {ctx.risk_count} 人（高等级 {len(high_warnings)} 人）："
            + "、".join(f"{row['name']}（{row['level']}）" for row in ctx.warnings[:6]) + "。"
            if ctx.risk_count else "当前无预警学生。"
        ),
        f"本课程教师评价方案：{_fmt_scheme(scheme, with_score=False)}。",
        f"附：较薄弱知识点 {_fmt_knowledge(weak_items, 3)}。" if weak_items else "附：知识点整体未见明显班级短板。",
    ]

    summary = " ".join(ctx.findings[:4])
    conclusion = (
        f"本报告侧重班级整体学情而非单个知识点。不及格 {fail_count} 人，"
        + ("成绩两端拉开，需要分层辅导。" if fail_count and ctx.excellent_rate >= 15 else "班级分数相对集中。")
        + (f"高等级预警以「{'；'.join((high_warnings[0].get('reasons') or [])[:2])}」为主。" if high_warnings else "")
        + f"历次均分走势为：{history_text}。"
    )
    suggestions = []
    if ctx.risk_count:
        names = "、".join(row["name"] for row in ctx.warnings[:5])
        suggestions.append(f"先处理预警学生（{names}），按成绩下滑 / 缺勤 / 作业缺交分流约谈。")
    if fail_count:
        suggestions.append(f"为不及格 {fail_count} 人建补习分组，对照最近考核「{exam}」错因，而不是全班重复讲已掌握内容。")
    if ctx.attendance_rate and ctx.attendance_rate < 90:
        suggestions.append(f"出勤率 {ctx.attendance_rate}%，把近两周缺勤名单与预警名单交叉核对。")
    if ctx.score_history and len(ctx.score_history) >= 2:
        prev, last = ctx.score_history[-2], ctx.score_history[-1]
        if last["score"] + 2 < prev["score"]:
            suggestions.append(f"「{last['name']}」班级均分较「{prev['name']}」下降，建议复盘该次命题覆盖的模块。")
    if ctx.excellent_rate >= 20:
        suggestions.append(f"优秀率 {ctx.excellent_rate}%，可给头部学生加综合题，避免课堂只盯不及格线。")
    if not suggestions:
        suggestions.append("维持现有班级节奏，下次考核后对比本次分档人数是否改善。")
    suggestion = "\n".join(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return _pack_report(ctx, summary, conclusion, suggestion)


def render_student_report(ctx: ReportContext) -> dict:
    """学生个人学情：画像标签、教师配置维度、个人成绩轨迹。"""
    weak_items = [item for item in ctx.knowledge_mastery if item["accuracy"] < 60]
    strong_items = [item for item in ctx.knowledge_mastery if item["accuracy"] >= 80]
    scheme = (ctx.eval_snapshot or {}).get("scheme") or []
    radar = ctx.radar or {}
    dim_text = "，".join(f"{name} {score}分" for name, score in radar.items()) or "暂无维度得分"
    tags_str = "、".join(ctx.tags) if ctx.tags else "暂无画像标签"
    history_text = "、".join(
        f"{item.get('name', '考核')} {item.get('score', '-')} 分" for item in ctx.score_history[-4:]
    ) or "暂无历次成绩"
    warning_text = "；".join(ctx.warnings[0]["reasons"]) if ctx.warnings else "未触发预警规则"
    lowest_dim = min(radar.items(), key=lambda item: item[1]) if radar else None

    ctx.findings = [
        f"【个人学情】{ctx.student_name}（{ctx.class_name}）《{ctx.course_name}》当前 {ctx.avg_score} 分，趋势{ctx.trend}。",
        f"教师配置维度得分：{dim_text}。方案明细：{_fmt_scheme(scheme)}。综合评价 {ctx.evaluation.get('total', '-')} 分，等级「{ctx.evaluation.get('level', '—')}」。",
        f"画像标签：{tags_str}。出勤率 {ctx.attendance_rate}%。",
        f"历次成绩：{history_text}。" + (f"预测下次约 {ctx.predicted_score} 分。" if ctx.predicted_score else ""),
        f"个人薄弱知识点：{_fmt_knowledge(weak_items)}；优势：{_fmt_knowledge(strong_items)}。",
        f"预警：{warning_text}。",
    ]
    summary = " ".join(ctx.findings[:4])
    conclusion = (
        f"个人报告以该生轨迹为主。{lowest_dim[0]}相对最低（{lowest_dim[1]}分），"
        if lowest_dim else "各配置维度得分接近。"
    ) + f"走势{ctx.trend}。{warning_text}。" + (
        f"知识点上优先补「{_fmt_knowledge(weak_items, 2)}」。" if weak_items else "知识点未出现明显个人短板。"
    )
    suggestions = []
    if lowest_dim:
        suggestions.append(f"针对教师指标「{lowest_dim[0]}」（{lowest_dim[1]}分）对照评价配置中的分项补强，而不是盲目刷题。")
    if weak_items:
        suggestions.append(
            f"本周完成「{weak_items[0]['name']}」专项练习，对照当前 {weak_items[0]['accuracy']}% 掌握度。"
        )
    if ctx.trend in ("下降", "下滑"):
        suggestions.append("近几次成绩下滑，约一次答疑，核对该阶段考核模块缺口。")
    if "出勤" in warning_text or ctx.attendance_rate < 90:
        suggestions.append(f"出勤率 {ctx.attendance_rate}%，缺课当天补笔记，避免态度分继续拉低综合评价。")
    if strong_items:
        suggestions.append(f"优势「{strong_items[0]['name']}」可做拓展题，保持标签中的正向特征。")
    if not suggestions:
        suggestions.append("保持现有节奏，每周一次错题复盘。")
    suggestion = "\n".join(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return _pack_report(ctx, summary, conclusion, suggestion)


def render_knowledge_report(ctx: ReportContext) -> dict:
    """知识点报告：按模块/知识点掌握度组织，弱化班级均分叙事。"""
    weak_items = [item for item in ctx.knowledge_mastery if item["accuracy"] < 60]
    strong_items = [item for item in ctx.knowledge_mastery if item["accuracy"] >= 80]
    mid_items = [item for item in ctx.knowledge_mastery if 60 <= item["accuracy"] < 80]
    ranked = ctx.knowledge_mastery
    lowest = ranked[0] if ranked else None
    highest = ranked[-1] if ranked else None
    by_module: dict[str, list[dict]] = defaultdict(list)
    for item in ctx.knowledge_mastery:
        by_module[item.get("module") or "未分模块"].append(item)
    module_lines = []
    for module, items in by_module.items():
        avg = round(sum(i["accuracy"] for i in items) / len(items), 1)
        names = "、".join(f"{i['name']}{i['accuracy']}%" for i in sorted(items, key=lambda x: x["accuracy"])[:4])
        module_lines.append(f"{module}（均 {avg}%）：{names}")

    ctx.findings = [
        f"【知识点分析】《{ctx.course_name}》覆盖 {len(ctx.knowledge_mastery)} 个知识点、{len(by_module)} 个模块。",
        f"优势 {len(strong_items)} 个、过渡 {len(mid_items)} 个、薄弱 {len(weak_items)} 个。",
        f"最低：「{lowest['name']}」{lowest['accuracy']}%（{lowest.get('module') or '未分模块'}）。" if lowest else "暂无掌握度数据。",
        f"最高：「{highest['name']}」{highest['accuracy']}%。" if highest else "",
        "按模块：" + "；".join(module_lines[:6]) + "。" if module_lines else "",
        f"薄弱清单：{_fmt_knowledge(weak_items, 8)}。" if weak_items else "没有低于 60% 的知识点。",
    ]
    ctx.findings = [item for item in ctx.findings if item]
    summary = (
        f"{ctx.findings[0]}{ctx.findings[1]}"
        + (f" 最需突破「{lowest['name']}」（{lowest['accuracy']}%）。" if lowest else "")
    )
    conclusion = (
        "本报告只讨论知识结构，不展开班级及格率。"
        + ("优势与薄弱同时偏多，适合按模块分层作业。" if len(weak_items) > 2 and len(strong_items) > 2
           else "薄弱面不宽，可按最低项逐个清零。" if len(weak_items) <= 2
           else "薄弱面偏宽，先保证主干知识点过 60%。")
        + (f"过渡区 {len(mid_items)} 个（{_fmt_knowledge(mid_items, 3)}）最容易短期抬升。" if mid_items else "")
    )
    suggestions = []
    for item in weak_items[:3]:
        module = item.get("module") or "对应模块"
        suggestions.append(f"「{item['name']}」（{module}，{item['accuracy']}%）安排专题课 + 当周测验。")
    if mid_items:
        suggestions.append(f"过渡点「{mid_items[0]['name']}」加课堂即时练，争取从 {mid_items[0]['accuracy']}% 升到 80%。")
    if strong_items:
        suggestions.append(f"「{strong_items[-1]['name']}」已达 {strong_items[-1]['accuracy']}%，可作范例，不必重复精讲。")
    if not suggestions:
        suggestions.append("两周后复测全部知识点掌握度，核对模块均分是否变化。")
    suggestion = "\n".join(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return _pack_report(ctx, summary, conclusion, suggestion, {"report_type": 3})


def render_quality_report(ctx: ReportContext) -> dict:
    """学习质量：严格按教师自定义评价维度、指标权重和学业构成来写。"""
    snapshot = ctx.eval_snapshot or {}
    scheme = snapshot.get("scheme") or []
    parts = snapshot.get("academicParts") or []
    level_dist = snapshot.get("levelDist") or {}
    eval_count = snapshot.get("evalCount") or (1 if ctx.scope == "student" else 0)
    radar = ctx.radar or {}
    lowest_dim = min(
        [(dim["name"], dim["score"]) for dim in scheme if dim.get("score") is not None],
        key=lambda item: item[1],
        default=None,
    )
    weakest_index = None
    for dim in scheme:
        for item in dim.get("indexes") or []:
            if item.get("score") is None:
                continue
            if weakest_index is None or item["score"] < weakest_index["score"]:
                weakest_index = {**item, "dimension": dim["name"]}
    weakest_part = None
    scored_parts = [item for item in parts if item.get("score") is not None]
    if scored_parts:
        weakest_part = min(scored_parts, key=lambda item: item["score"])
    dist_text = "、".join(f"{name} {count}人" for name, count in level_dist.items()) or "暂无已落库等级分布"
    who = f"{ctx.student_name}" if ctx.scope == "student" else f"{ctx.class_name or '本班'}（已评价 {eval_count} 人）"

    ctx.findings = [
        f"【学习质量】依据《{ctx.course_name}》任课教师自定义评价方案评估{who}。",
        f"配置维度：{_fmt_scheme(scheme)}。",
        f"学业水平构成（教师可调配比）：{_fmt_parts(parts)}。",
        f"综合评价 {ctx.evaluation.get('total', ctx.avg_score)} 分，等级「{ctx.evaluation.get('level') or _level_by_score(ctx.avg_score)}」。",
        f"等级分布：{dist_text}。" if ctx.scope == "class" else f"出勤率 {ctx.attendance_rate}%。",
        f"当前最低维度：{lowest_dim[0]} {lowest_dim[1]}分。" if lowest_dim else "各配置维度暂无足够得分样本。",
    ]
    summary = " ".join(ctx.findings[:4])
    conclusion = (
        "质量报告只解读教师配置的维度和指标，不把一次期末分数当成全部质量。"
        + (f"短板在「{lowest_dim[0]}」。" if lowest_dim else "")
        + (f"分项「{weakest_index['dimension']}-{weakest_index['name']}」仅 {weakest_index['score']} 分（权重 {weakest_index['weight']}%）。" if weakest_index else "")
        + (f"学业构成中「{weakest_part['name']}」均分 {weakest_part['score']}，但权重 {weakest_part['weight']}%，对总分影响大。" if weakest_part else "")
    )
    suggestions = []
    if weakest_part and weakest_part.get("weight", 0) >= 20 and (weakest_part.get("score") or 100) < 75:
        suggestions.append(
            f"「{weakest_part['name']}」权重大（{weakest_part['weight']}%）且均分 {weakest_part['score']}，优先补该构成，而不是平均用力。"
        )
    if weakest_index:
        suggestions.append(
            f"对照评价配置，把「{weakest_index['dimension']} / {weakest_index['name']}」纳入下周质量跟踪。"
        )
    if lowest_dim:
        suggestions.append(f"课堂和作业设计向「{lowest_dim[0]}」倾斜，因其是教师方案中当前最低维。")
    if ctx.scope == "class" and level_dist.get("不合格"):
        suggestions.append(f"不合格 {level_dist['不合格']} 人，按教师方案复算其学业构成短板后再分组。")
    if not scheme:
        suggestions.append("请先在评价配置中维护本课程维度与指标，质量报告才能按你的权重出分。")
    suggestions.append("配置变更后系统会按新权重重算学习质量，建议以重算结果为准复核本报告。")
    suggestion = "\n".join(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return _pack_report(ctx, summary, conclusion, suggestion, {"report_type": 4})


def render_report(ctx: ReportContext) -> dict:
    """模板兜底入口（按 report_type 分发）。"""
    if ctx.report_type == 2:
        return render_student_report(ctx)
    if ctx.report_type == 3:
        return render_knowledge_report(ctx)
    if ctx.report_type == 4:
        return render_quality_report(ctx)
    if ctx.scope == "student":
        return render_student_report(ctx)
    return render_class_report(ctx)
