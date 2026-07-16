"""D05 知识点掌握度等级（固定阈值三档）。

等级规则：
    ≥ 80  良好（绿）
    60-80 一般（黄）
    < 60  薄弱（红）

数据来源：
    - 考试题目标注知识点 + AI 答题记录（StudentAnswerRecord + AiQuestion.point_id）
    - 兜底：KnowledgeMastery 表的 mastery_score
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_
from sqlmodel import Session, func, select

from app.models import (
    AiQuestion,
    AnswerTask,
    CourseStudent,
    KnowledgeMastery,
    KnowledgeModule,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
)
from app.models.question import TASK_TYPE_ASSIGNMENT


@dataclass
class MasteryStat:
    point_id: int
    point_name: str
    module_name: str
    accuracy: float       # 正确率 0-100
    level: str            # 良好 / 一般 / 薄弱
    color: str            # green / yellow / red


def accuracy_to_level(accuracy: float) -> tuple[str, str]:
    """正确率 → (等级, 颜色)。"""
    if accuracy >= 80:
        return "良好", "green"
    if accuracy >= 60:
        return "一般", "yellow"
    return "薄弱", "red"


def compute_student_mastery(
    session: Session, student_id: int, course_id: int
) -> list[MasteryStat]:
    """某学生该课程下所有知识点的掌握度（基于答题记录）。

    无答题记录时，回退到 KnowledgeMastery 表的 mastery_score。
    """
    # 课程所有知识点
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_map = {m.module_id: m.module_name for m in modules}
    module_ids = list(module_map.keys())
    if not module_ids:
        return []
    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all()
    if not points:
        return []

    results: list[MasteryStat] = []
    for p in points:
        # 优先用答题记录
        total, correct = session.exec(
            select(
                func.count(StudentAnswerRecord.answer_id),
                func.sum(StudentAnswerRecord.is_correct),
            )
            .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
            .where(
                StudentAnswerRecord.student_id == student_id,
                AiQuestion.course_id == course_id,
                AiQuestion.point_id == p.point_id,
            )
        ).one()

        if total and total > 0:
            accuracy = (correct or 0) * 100.0 / total
        else:
            # 兜底：KnowledgeMastery 表
            km = session.exec(
                select(KnowledgeMastery).where(
                    KnowledgeMastery.student_id == student_id,
                    KnowledgeMastery.course_id == course_id,
                    KnowledgeMastery.point_id == p.point_id,
                )
            ).first()
            accuracy = km.mastery_score if km else 0.0

        level, color = accuracy_to_level(accuracy)
        results.append(
            MasteryStat(
                point_id=p.point_id,
                point_name=p.point_name,
                module_name=module_map.get(p.module_id, ""),
                accuracy=round(accuracy, 1),
                level=level,
                color=color,
            )
        )
    return results


def refresh_student_mastery(session: Session, student_id: int, course_id: int) -> None:
    """按该生全部答题记录刷新持久化个人掌握度。"""
    session.flush()
    rows = session.exec(
        select(
            AiQuestion.point_id,
            func.count(StudentAnswerRecord.answer_id),
            func.sum(StudentAnswerRecord.is_correct),
        )
        .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
        .where(
            StudentAnswerRecord.student_id == student_id,
            AiQuestion.course_id == course_id,
        )
        .group_by(AiQuestion.point_id)
    ).all()

    for point_id, total, correct in rows:
        if not total:
            continue
        score = round((correct or 0) * 100.0 / total, 1)
        mastery = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.course_id == course_id,
                KnowledgeMastery.student_id == student_id,
                KnowledgeMastery.point_id == point_id,
            )
        ).first()
        if not mastery:
            mastery = KnowledgeMastery(
                course_id=course_id,
                student_id=student_id,
                point_id=point_id,
                mastery_score=score,
                mastery_level=_mastery_level(score),
            )
        else:
            mastery.mastery_score = score
            mastery.mastery_level = _mastery_level(score)
            mastery.update_time = datetime.now()
        session.add(mastery)


def compute_mastery_index_with_fallback(
    session: Session,
    course_id: int,
    student_ids: list[int],
) -> dict[tuple[int, int], float]:
    """教师/管理员视角：优先答题记录，无记录时回退到 KnowledgeMastery 表。

    这样即使学生没有答题记录（如预注入的演示数据），教师也能看到
    知识点掌握度热力图，而不是全为 0。
    """
    answer_index = compute_assignment_accuracy_index(session, course_id, student_ids)

    # 收集 answer_index 中已有的 (student_id, point_id) 组合
    answered_pairs = set(answer_index.keys())

    # KnowledgeMastery 回退（仅填充缺失项）
    if answered_pairs:
        answered_students = {sid for sid, _ in answered_pairs}
        answered_points = {pid for _, pid in answered_pairs}
        fully_missed_students = [sid for sid in student_ids if sid not in answered_students]
    else:
        fully_missed_students = list(student_ids)
        answered_points = set()

    if fully_missed_students or True:  # 始终检查 KnowledgeMastery 兜底
        km_records = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.course_id == course_id,
                KnowledgeMastery.student_id.in_(student_ids),  # type: ignore
            )
        ).all()
        for km in km_records:
            pair = (km.student_id, km.point_id)
            if pair not in answer_index:
                answer_index[pair] = km.mastery_score

    return answer_index


def compute_assignment_accuracy_index(
    session: Session,
    course_id: int,
    student_ids: list[int],
) -> dict[tuple[int, int], float]:
    """计算教师任务的学生/知识点正确率，严格排除自主练习。"""
    if not student_ids:
        return {}
    rows = session.exec(
        select(
            StudentAnswerRecord.student_id,
            AiQuestion.point_id,
            func.count(StudentAnswerRecord.answer_id),
            func.sum(StudentAnswerRecord.is_correct),
        )
        .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
        .outerjoin(AnswerTask, StudentAnswerRecord.task_id == AnswerTask.task_id)
        .where(
            StudentAnswerRecord.student_id.in_(student_ids),  # type: ignore
            AiQuestion.course_id == course_id,
            or_(
                AnswerTask.task_id.is_(None),
                AnswerTask.task_type == TASK_TYPE_ASSIGNMENT,
            ),
        )
        .group_by(StudentAnswerRecord.student_id, AiQuestion.point_id)
    ).all()
    return {
        (student_id, point_id): round((correct or 0) * 100.0 / total, 1)
        for student_id, point_id, total, correct in rows
        if total
    }


def compute_class_mastery(
    session: Session, course_id: int, class_id: int | None = None
) -> list[MasteryStat]:
    """班级视角：按知识点聚合所有学生的平均正确率。"""
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_map = {m.module_id: m.module_name for m in modules}
    module_ids = list(module_map.keys())
    if not module_ids:
        return []
    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all()
    if not points:
        return []

    stmt = (
        select(CourseStudent.student_id)
        .join(Student, CourseStudent.student_id == Student.student_id)
        .where(CourseStudent.course_id == course_id)
    )
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    student_ids = list(session.exec(stmt).all())
    accuracy_index = compute_assignment_accuracy_index(session, course_id, student_ids)

    results: list[MasteryStat] = []
    for p in points:
        accs = [
            accuracy_index[(sid, p.point_id)]
            for sid in student_ids
            if (sid, p.point_id) in accuracy_index
        ]
        avg_acc = sum(accs) / len(accs) if accs else 0.0

        level, color = accuracy_to_level(avg_acc)
        results.append(
            MasteryStat(
                point_id=p.point_id,
                point_name=p.point_name,
                module_name=module_map.get(p.module_id, ""),
                accuracy=round(avg_acc, 1),
                level=level,
                color=color,
            )
        )
    return results


def _mastery_level(score: float) -> int:
    if score >= 80:
        return 3
    if score >= 60:
        return 2
    return 1
