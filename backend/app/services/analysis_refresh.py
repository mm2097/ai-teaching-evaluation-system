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
    EvalDimensionScore,
    StudentProfile,
    StudentEvaluationResult,
    StudyWarning,
)
from app.services.evaluation import compute_evaluation, persist_evaluation
from app.services.mastery import compute_student_mastery, refresh_student_mastery
from app.services.profile import compute_class_slopes, compute_profile
from app.services.tag import generate_tags
from app.services.warning import evaluate_student, persist_warnings, warning_type_for_hit
from app.services.ct_achievement import refresh_ct_achievement


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
    class_slopes: list[float] | None = None,
    profile=None,
    refresh_tags: bool = True,
) -> None:
    """计算并写入/更新学情画像（三维度 + 标签 + 模块优劣势）。

    class_slopes / profile 供批量刷新复用，避免重复计算。
    refresh_tags=False 时仅更新三维度得分，保留已有标签与模块优劣势
    （标签与优劣势不依赖评价配置，配置变化重算时无需重生成）。
    """
    if profile is None:
        if class_slopes is None:
            profile = compute_profile(session, student_id, course_id)
        else:
            profile = compute_profile(session, student_id, course_id, class_slopes=class_slopes)
    if refresh_tags:
        tags = generate_tags(session, student_id, course_id)
        good_modules, weak_modules = derive_module_strengths(session, student_id, course_id)
    else:
        tags, good_modules, weak_modules = None, None, None

    existing = session.exec(
        select(StudentProfile).where(
            StudentProfile.course_id == course_id,
            StudentProfile.student_id == student_id,
        )
    ).first()

    availability = profile.data_availability or {}
    available_scores = [
        score for key, score in (
            ("academic", profile.academic_score),
            ("attitude", profile.attitude_score),
            ("progress", profile.progress_score),
        )
        if availability.get(key, False)
    ]
    if not available_scores:
        if existing:
            session.delete(existing)
            session.commit()
        return
    total = round(sum(available_scores) / len(available_scores), 1)

    if existing:
        existing.academic_score = profile.academic_score
        existing.attitude_score = profile.attitude_score
        existing.progress_score = profile.progress_score
        existing.total_profile_score = total
        if refresh_tags:
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


def invalidate_course_analysis(session: Session, course_id: int) -> None:
    """源数据变化后立即清除派生快照，避免后台重算期间返回旧结果。"""
    evaluations = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.course_id == course_id
        )
    ).all()
    eval_ids = [row.eval_id for row in evaluations if row.eval_id is not None]
    if eval_ids:
        for row in session.exec(
            select(EvalDimensionScore).where(
                EvalDimensionScore.eval_id.in_(eval_ids)  # type: ignore[arg-type]
            )
        ).all():
            session.delete(row)
    for row in evaluations:
        session.delete(row)
    for row in session.exec(
        select(StudentProfile).where(StudentProfile.course_id == course_id)
    ).all():
        session.delete(row)
    for row in session.exec(
        select(StudyWarning).where(
            StudyWarning.course_id == course_id,
            StudyWarning.handle_status == 0,
        )
    ).all():
        session.delete(row)
    session.commit()


def refresh_student_analysis(session: Session, student_id: int, course_id: int) -> None:
    """同步刷新单个学生受源数据影响的掌握度、画像、评价和预警。"""
    refresh_student_mastery(session, student_id, course_id)
    profile = compute_profile(session, student_id, course_id)
    upsert_student_profile(
        session, student_id, course_id, profile=profile, refresh_tags=True
    )
    result = compute_evaluation(session, student_id, course_id, profile=profile)
    persist_evaluation(session, student_id, course_id, result=result)

    for warning in session.exec(
        select(StudyWarning).where(
            StudyWarning.course_id == course_id,
            StudyWarning.student_id == student_id,
            StudyWarning.handle_status == 0,
        )
    ).all():
        session.delete(warning)
    weak_points = [
        (item.point_name, item.accuracy)
        for item in compute_student_mastery(session, student_id, course_id)
        if item.accuracy < 60
    ]
    warning_result = evaluate_student(
        session, student_id, course_id, len(weak_points), weak_points
    )
    for hit in warning_result.hits:
        session.add(StudyWarning(
            course_id=course_id,
            student_id=student_id,
            warning_type=warning_type_for_hit(hit),
            warning_level=warning_result.level_code,
            warning_reason=hit.reason[:255],
            handle_status=0,
        ))
    session.commit()


# ============================================================================
# 主编排函数
# ============================================================================

def refresh_course_analysis(session: Session, course_id: int) -> dict:
    """刷新课程内所有学生的全部分析数据。

    执行顺序：
      1. 知识点掌握度 → 按当前答题记录 + 考试扣分完整重建
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

    # 班级斜率分布取一次复用（D04 进步分归一化，避免逐学生重复计算）
    class_slopes = compute_class_slopes(session, course_id)

    for sid in student_ids:
        # 1. 知识点掌握度只由当前答题/分题扣分产生，不再用课程均分补值。
        total_mastery += refresh_student_mastery(session, sid, course_id)

        # 2. 学情画像
        upsert_student_profile(session, sid, course_id, class_slopes=class_slopes)

        # 3. 学习质量评价
        persist_evaluation(session, sid, course_id, class_slopes=class_slopes)

        # 4. 预警扫描
        weak_points = [
            (item.point_name, item.accuracy)
            for item in compute_student_mastery(session, sid, course_id)
            if item.accuracy < 60
        ]
        wr = evaluate_student(
            session, sid, course_id, len(weak_points), weak_points
        )
        if wr.hits:
            warning_results.append(wr)

    warnings_count = persist_warnings(session, warning_results, course_id)

    # 5. 课程目标达成度（CT1-CT8，失败不阻断主流程）
    try:
        refresh_ct_achievement(session, course_id)
    except Exception:
        pass

    return {
        "students_processed": len(student_ids),
        "profiles_updated": len(student_ids),
        "mastery_filled": total_mastery,
        "evaluations_updated": len(student_ids),
        "warnings_created": warnings_count,
    }


def refresh_course_evaluations(session: Session, course_id: int) -> dict:
    """评价配置变化后重算学情画像与学习质量评价。

    教师调整评价维度/指标/权重（eval_config API）后调用，把新配置反映到：
      - StudentProfile（学业水平配比影响画像三维度）
      - StudentEvaluationResult + EvalDimensionScore（「学生学习质量评价」页数据源）

    预警与知识点掌握度不依赖评价配置，无需重算。
    """
    student_ids = session.exec(
        select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    ).all()
    if not student_ids:
        return {"students_processed": 0, "evaluations_updated": 0}

    # 班级斜率分布取一次复用（避免逐学生重复收集）
    class_slopes = compute_class_slopes(session, course_id)
    for sid in student_ids:
        profile = compute_profile(session, sid, course_id, class_slopes=class_slopes)
        result = compute_evaluation(
            session, sid, course_id, class_slopes=class_slopes, profile=profile
        )
        persist_evaluation(session, sid, course_id, result=result)
        # 画像只更新三维度得分（标签/模块优劣势不受评价配置影响）
        upsert_student_profile(
            session, sid, course_id, class_slopes=class_slopes,
            profile=profile, refresh_tags=False,
        )

    return {
        "students_processed": len(student_ids),
        "evaluations_updated": len(student_ids),
    }
