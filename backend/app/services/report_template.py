"""D10 报告结论与建议 - 模板兜底（必走）。

LLM 增强在 algorithm/src/reporter.py，失败回退此模块输出。
两种报告：班级报告 / 学生个人报告。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    Course,
    CourseStudent,
    ExamBatch,
    ScoreRecord,
    Student,
)
from app.services.mastery import compute_class_mastery, compute_student_mastery
from app.services.profile import compute_profile
from app.services.tag import generate_tags
from app.services.warning import evaluate_student


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


def build_class_context(
    session: Session, course_id: int, class_id: Optional[int] = None,
    report_type: int = 1,
) -> ReportContext:
    """构建班级报告上下文。"""
    course = session.get(Course, course_id)
    ctx = ReportContext(
        scope="class",
        report_type=report_type,
        course_id=course_id,
        course_name=course.course_name if course else "",
        class_name="",
    )

    # 学生范围
    stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    if class_id:
        in_class = session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all()
        stmt = stmt.where(CourseStudent.student_id.in_(in_class))  # type: ignore
    sids = session.exec(stmt).all()
    if not sids:
        return ctx

    # 班级最近一次 batch 成绩统计
    batches = session.exec(
        select(ExamBatch).where(ExamBatch.course_id == course_id).order_by(ExamBatch.exam_time)
    ).all()
    if batches:
        last = batches[-1]
        scores = session.exec(
            select(ScoreRecord.score).where(
                ScoreRecord.batch_id == last.batch_id,
                ScoreRecord.student_id.in_(sids),  # type: ignore
            )
        ).all()
        if scores:
            ctx.avg_score = round(sum(scores) / len(scores), 1)
            ctx.pass_rate = round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1)
            ctx.excellent_rate = round(sum(1 for s in scores if s >= 85) / len(scores) * 100, 1)

    # 知识点薄弱
    class_mastery = compute_class_mastery(session, course_id, class_id)
    ctx.weak_points = [m.point_name for m in class_mastery if m.accuracy < 60]
    ctx.strong_points = [m.point_name for m in class_mastery if m.accuracy >= 80]

    return ctx


def build_student_context(
    session: Session, student_id: int, course_id: int
) -> ReportContext:
    """构建学生报告上下文。"""
    course = session.get(Course, course_id)
    student = session.get(Student, student_id)
    from app.models import ClassInfo
    cls = session.get(ClassInfo, student.class_id) if student else None

    ctx = ReportContext(
        scope="student",
        course_id=course_id,
        course_name=course.course_name if course else "",
        student_id=student_id,
        student_name=student.real_name if student else "",
        class_name=cls.class_name if cls else "",
    )

    # 三维度画像
    profile = compute_profile(session, student_id, course_id)
    ctx.radar = {
        "学业成绩": profile.academic_score,
        "学习态度": profile.attitude_score,
        "学习进步": profile.progress_score,
    }

    # 知识点
    masteries = compute_student_mastery(session, student_id, course_id)
    ctx.weak_points = [m.point_name for m in masteries if m.accuracy < 60]
    ctx.strong_points = [m.point_name for m in masteries if m.accuracy >= 80]

    # 标签
    ctx.tags = generate_tags(session, student_id, course_id)

    # 趋势
    from app.services.predict import predict_student_scores
    pred = predict_student_scores(session, student_id, course_id)
    ctx.trend = pred.get("trend", "稳定")
    ctx.avg_score = pred.get("current", 0.0)

    return ctx


# ===== 模板兜底文本生成 =====

def render_class_report(ctx: ReportContext) -> dict:
    """班级报告模板。"""
    weak_str = "、".join(ctx.weak_points[:5]) if ctx.weak_points else "暂无"
    top_weak = ctx.weak_points[0] if ctx.weak_points else "各知识点"

    summary = (
        f"本期班级均分 {ctx.avg_score}，及格率 {ctx.pass_rate}%，"
        f"优秀率 {ctx.excellent_rate}%。整体表现{'良好' if ctx.avg_score >= 75 else '一般' if ctx.avg_score >= 60 else '偏低'}。"
    )
    conclusion = (
        f"薄弱知识点：{weak_str}。"
        + ("整体掌握度较好，可适度加快教学进度。" if not ctx.weak_points
           else "存在明显薄弱环节，需重点干预。")
    )
    suggestion = (
        f"建议：针对「{top_weak}」开展专题复习，配合课堂互动巩固。"
        + ("同时为优等生设计拓展任务。" if ctx.excellent_rate > 30
           else "对学困生安排一对一辅导。" if ctx.pass_rate < 80 else "")
    )
    return {
        "scope": "class",
        "summary": summary,
        "conclusion": conclusion,
        "suggestion": suggestion,
        "source": "template",
    }


def render_student_report(ctx: ReportContext) -> dict:
    """学生报告模板。"""
    tags_str = "、".join(ctx.tags) if ctx.tags else "暂无"
    weak_str = "、".join(ctx.weak_points[:3]) if ctx.weak_points else "暂无"
    strong_str = "、".join(ctx.strong_points[:3]) if ctx.strong_points else "暂无"

    summary = (
        f"{ctx.student_name}（{ctx.class_name}）在《{ctx.course_name}》"
        f"中当前成绩 {ctx.avg_score} 分，趋势{ctx.trend}。"
        f"标签：{tags_str}。"
    )
    conclusion = (
        f"优势知识点：{strong_str}；薄弱知识点：{weak_str}。"
        + ("学习状态稳定，建议保持。" if "稳定型" in ctx.tags
           else "需关注学习状态变化。" if "下滑预警" in ctx.tags
           else "进步明显，可适当提升难度。" if "进步显著" in ctx.tags
           else "学习状态待持续观察。")
    )
    suggestion = (
        f"建议："
        + (f"针对「{ctx.weak_points[0]}」做专项练习；" if ctx.weak_points else "巩固现有知识点；")
        + ("加强出勤管理。" if "出勤风险" in ctx.tags else "保持课堂参与度。")
    )
    return {
        "scope": "student",
        "summary": summary,
        "conclusion": conclusion,
        "suggestion": suggestion,
        "source": "template",
    }


def render_knowledge_report(ctx: ReportContext) -> dict:
    """课程知识点分析报告模板。"""
    # 按掌握度排序，取前 5 薄弱和前 5 优势
    weak_top5 = ctx.weak_points[:5] if ctx.weak_points else ["暂无"]
    strong_top5 = ctx.strong_points[:5] if ctx.strong_points else ["暂无"]
    weak_count = len(ctx.weak_points)
    strong_count = len(ctx.strong_points)

    summary = (
        f"《{ctx.course_name}》知识点分析："
        f"优势知识点 {strong_count} 个，薄弱知识点 {weak_count} 个。"
        f"班级均分 {ctx.avg_score}，及格率 {ctx.pass_rate}%。"
    )
    conclusion = (
        f"薄弱知识点：{'、'.join(weak_top5)}。"
        + (f"优势知识点：{'、'.join(strong_top5)}。" if strong_top5[0] != "暂无" else "")
        + ("知识点掌握两极分化明显，需分层教学。" if weak_count > 3 and strong_count > 3
           else "整体知识点掌握较为均衡。" if weak_count <= 2
           else "薄弱知识点较多，需加强基础教学。")
    )
    suggestion = (
        f"教学建议："
        + (f"对「{ctx.weak_points[0]}」进行专题突破，配合课堂练习巩固；" if ctx.weak_points else "")
        + (f"对「{ctx.strong_points[0]}」可适当拓展深度，设计挑战性任务。" if ctx.strong_points else "")
        + "建议每周安排一次知识点复盘测试，跟踪薄弱点的改善情况。"
    )
    return {
        "scope": "class",
        "report_type": 3,
        "summary": summary,
        "conclusion": conclusion,
        "suggestion": suggestion,
        "source": "template",
    }


def render_quality_report(ctx: ReportContext) -> dict:
    """学生学习质量报告模板（班级维度）。"""
    level = "良好" if ctx.avg_score >= 75 else "一般" if ctx.avg_score >= 60 else "偏低"
    summary = (
        f"《{ctx.course_name}》学习质量评价："
        f"班级均分 {ctx.avg_score}，整体水平{level}。"
        f"及格率 {ctx.pass_rate}%，优秀率 {ctx.excellent_rate}%。"
    )
    conclusion = (
        f"学业水平：均分 {ctx.avg_score}，"
        + ("大部分学生达到良好以上水平。" if ctx.excellent_rate >= 30
           else "多数学生处于及格线附近，整体水平有待提升。" if ctx.pass_rate < 80
           else "整体学业水平中等。")
        + (f"知识掌握：薄弱点集中在{'、'.join(ctx.weak_points[:3])}。" if ctx.weak_points else "")
    )
    suggestion = (
        f"质量提升建议："
        + ("针对优秀率偏低的问题，为前30%学生提供拓展学习资源；" if ctx.excellent_rate < 20 else "")
        + ("针对及格率偏低的问题，对学困生实施一对一帮扶计划；" if ctx.pass_rate < 70 else "")
        + "建立学习质量跟踪档案，每月评估一次各维度变化趋势。"
    )
    return {
        "scope": "class",
        "report_type": 4,
        "summary": summary,
        "conclusion": conclusion,
        "suggestion": suggestion,
        "source": "template",
    }


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
