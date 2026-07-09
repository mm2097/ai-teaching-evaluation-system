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

from sqlmodel import Session, func, select

from app.models import (
    AiQuestion,
    CourseStudent,
    KnowledgeMastery,
    KnowledgeModule,
    KnowledgePoint,
    StudentAnswerRecord,
)


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

    # 选学生（class_id 筛选交由调用方处理，这里只取课程全体）
    stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    student_ids = session.exec(stmt).all()

    results: list[MasteryStat] = []
    for p in points:
        accs: list[float] = []
        for sid in student_ids:
            total, correct = session.exec(
                select(
                    func.count(StudentAnswerRecord.answer_id),
                    func.sum(StudentAnswerRecord.is_correct),
                )
                .join(AiQuestion, StudentAnswerRecord.question_id == AiQuestion.question_id)
                .where(
                    StudentAnswerRecord.student_id == sid,
                    AiQuestion.point_id == p.point_id,
                )
            ).one()
            if total and total > 0:
                accs.append((correct or 0) * 100.0 / total)

        if accs:
            avg_acc = sum(accs) / len(accs)
        else:
            # 兜底：KnowledgeMastery 班级均值
            kms = session.exec(
                select(KnowledgeMastery.mastery_score)
                .where(
                    KnowledgeMastery.course_id == course_id,
                    KnowledgeMastery.point_id == p.point_id,
                )
            ).all()
            avg_acc = sum(kms) / len(kms) if kms else 0.0

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
