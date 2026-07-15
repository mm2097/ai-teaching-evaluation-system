"""上传数据后自动刷新课程分析数据。

当任课教师通过教学数据接口上传成绩/考勤文件后，
调用 refresh_course_analysis() 自动重新计算并入库：
  - 知识点掌握度（KnowledgeMastery）
  - 学情画像（StudentProfile）：三维度得分 + 标签 + 模块优劣势
  - 学习质量评价（StudentEvaluationResult + EvalDimensionScore）
  - 学情预警（StudyWarning）

这样前端 /analysis/profile 等接口可以立即查到最新分析结果。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import (
    CourseStudent,
    KnowledgeMastery,
    KnowledgeModule,
    KnowledgePoint,
    StudentProfile,
)
from app.services.evaluation import persist_evaluation
from app.services.mastery import compute_student_mastery
from app.services.profile import compute_profile
from app.services.tag import generate_tags
from app.services.warning import evaluate_student, persist_warnings


# ============================================================================
# 知识点掌握度估算
# ============================================================================

def _estimate_mastery_from_scores(
    session: Session, student_id: int, course_id: int
) -> float:
    """基于该学生该课程所有成绩记录估算平均掌握度（0-100）。

    从 ScoreRecord / IndividualScore / CourseTestDetail 三张表汇总。
    无成绩数据时返回 0（后续以答题记录或其他来源补）。
    """
    from app.models import CourseTestDetail, IndividualScore, ScoreRecord

    all_scores: list[float] = []

    # ScoreRecord（旧表兼容）
    scores = session.exec(
        select(ScoreRecord.score).where(
            ScoreRecord.student_id == student_id,
            ScoreRecord.course_id == course_id,
        )
    ).all()
    all_scores.extend(float(s) for s in scores)

    # 新表需通过 ExamBatch 关联到课程
    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    if batch_ids:
        # IndividualScore
        ind_scores = session.exec(
            select(IndividualScore.score).where(
                IndividualScore.student_id == student_id,
                IndividualScore.exam_batch_id.in_(batch_ids),
            )
        ).all()
        all_scores.extend(float(s) for s in ind_scores)

        # CourseTestDetail
        dtl_scores = session.exec(
            select(CourseTestDetail.total_score).where(
                CourseTestDetail.student_id == student_id,
                CourseTestDetail.exam_batch_id.in_(batch_ids),
            )
        ).all()
        all_scores.extend(float(s) for s in dtl_scores)

    if not all_scores:
        return 0.0
    return round(sum(all_scores) / len(all_scores), 1)


def upsert_knowledge_mastery(
    session: Session, student_id: int, course_id: int
) -> int:
    """为学生课程内所有知识点补充估算掌握度（仅填充缺失项）。

    已有真实答题记录计算出的 KnowledgeMastery 记录不覆盖；
    缺失的知识点用成绩均值估算填充，保证每个知识点都有一条记录。
    返回新写入条数。
    """
    # 获取课程下所有知识点
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_ids = [m.module_id for m in modules]
    if not module_ids:
        return 0

    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore[arg-type]
    ).all()
    if not points:
        return 0

    avg_score = _estimate_mastery_from_scores(session, student_id, course_id)

    written = 0
    for p in points:
        existing = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.course_id == course_id,
                KnowledgeMastery.student_id == student_id,
                KnowledgeMastery.point_id == p.point_id,
            )
        ).first()

        if existing:
            continue  # 已有记录（来自答题计算或之前估算），不动

        level = 3 if avg_score >= 80 else (2 if avg_score >= 60 else 1)
        session.add(KnowledgeMastery(
            course_id=course_id,
            student_id=student_id,
            point_id=p.point_id,
            mastery_score=avg_score,
            mastery_level=level,
        ))
        written += 1

    if written:
        session.commit()
    return written


# ============================================================================
# 模块优劣势推导
# ============================================================================

def derive_module_strengths(
    session: Session, student_id: int, course_id: int
) -> tuple[str, str]:
    """从知识点掌握度聚合出课程内模块优劣势。

    返回 (good_modules_csv, weak_modules_csv)。
    阈值：平均 ≥ 80 为优势、< 60 为薄弱。
    """
    stats = compute_student_mastery(session, student_id, course_id)
    if not stats:
        return "", ""

    # 按模块名聚合
    module_scores: dict[str, list[float]] = {}
    for s in stats:
        if s.module_name:
            module_scores.setdefault(s.module_name, []).append(s.accuracy)

    good: list[str] = []
    weak: list[str] = []
    for name, accs in module_scores.items():
        avg = sum(accs) / len(accs)
        if avg >= 80:
            good.append(name)
        elif avg < 60:
            weak.append(name)

    return ", ".join(good), ", ".join(weak)


# ============================================================================
# 画像入库
# ============================================================================

def upsert_student_profile(
    session: Session, student_id: int, course_id: int,
) -> None:
    """计算并写入/更新学情画像（三维度 + 标签 + 模块优劣势）。"""
    profile = compute_profile(session, student_id, course_id)
    tags = generate_tags(session, student_id, course_id)
    good_modules, weak_modules = derive_module_strengths(session, student_id, course_id)

    total = round(
        (profile.academic_score + profile.attitude_score + profile.progress_score) / 3, 1
    )

    existing = session.exec(
        select(StudentProfile).where(
            StudentProfile.course_id == course_id,
            StudentProfile.student_id == student_id,
        )
    ).first()

    if existing:
        existing.academic_score = profile.academic_score
        existing.attitude_score = profile.attitude_score
        existing.progress_score = profile.progress_score
        existing.total_profile_score = total
        existing.study_tags = ", ".join(tags) if tags else None
        existing.good_modules = good_modules or None
        existing.weak_modules = weak_modules or None
        existing.update_time = datetime.now()
        session.add(existing)
    else:
        session.add(StudentProfile(
            course_id=course_id,
            student_id=student_id,
            academic_score=profile.academic_score,
            attitude_score=profile.attitude_score,
            progress_score=profile.progress_score,
            total_profile_score=total,
            study_tags=", ".join(tags) if tags else None,
            good_modules=good_modules or None,
            weak_modules=weak_modules or None,
        ))
    session.commit()


# ============================================================================
# 主编排函数
# ============================================================================

def refresh_course_analysis(session: Session, course_id: int) -> dict:
    """刷新课程内所有学生的全部分析数据。

    执行顺序：
      1. 知识点掌握度 → 填充缺失项
      2. 学情画像     → 三维度 + 标签 + 模块优劣势
      3. 学习质量评价 → 四维度加权 + 等级
      4. 学情预警     → 规则扫描 + 入库

    Returns:
        {students_processed, profiles_updated, mastery_filled,
         evaluations_updated, warnings_created}
    """
    student_ids = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()

    if not student_ids:
        return {
            "students_processed": 0,
            "profiles_updated": 0,
            "mastery_filled": 0,
            "evaluations_updated": 0,
            "warnings_created": 0,
        }

    total_mastery = 0
    warning_results: list = []

    for sid in student_ids:
        # 1. 知识点掌握度（仅填充缺失项）
        total_mastery += upsert_knowledge_mastery(session, sid, course_id)

        # 2. 学情画像
        upsert_student_profile(session, sid, course_id)

        # 3. 学习质量评价
        persist_evaluation(session, sid, course_id)

        # 4. 预警扫描
        weak_count = sum(
            1 for s in compute_student_mastery(session, sid, course_id)
            if s.accuracy < 60
        )
        wr = evaluate_student(session, sid, course_id, weak_count)
        if wr.hits:
            warning_results.append(wr)

    warnings_count = persist_warnings(session, warning_results, course_id)

    return {
        "students_processed": len(student_ids),
        "profiles_updated": len(student_ids),
        "mastery_filled": total_mastery,
        "evaluations_updated": len(student_ids),
        "warnings_created": warnings_count,
    }
