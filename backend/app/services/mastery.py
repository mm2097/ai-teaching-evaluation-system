"""D05 知识点掌握度等级（固定阈值三档）。

等级规则：
    ≥ 80  良好（绿）
    60-80 一般（黄）
    < 60  薄弱（红）

数据来源：
    - 考试题目标注知识点 + AI 答题记录（StudentAnswerRecord + AiQuestion.point_id）
    - 课程测试各题扣分（CourseTestDetail.question{1..5}_score/_knowledge）
      按扣分知识点折算掌握度，与答题正确率并存时取平均
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
    CourseTestDetail,
    ExamBatch,
    KnowledgeMastery,
    KnowledgeModule,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
)
from app.models.question import TASK_TYPE_ASSIGNMENT
from app.services.knowledge_utils import split_knowledge_names

# 课程测试模板固定 5 大题，按满分 100 分均摊：每题满分 20 分。
# 每题掌握度 = (20 - 该题扣分) / 20 * 100；
# 一格多个知识点时扣分与可得分均摊到各知识点。
EXAM_QUESTION_FULL_SCORE = 20.0


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


def compute_exam_mastery_indexes(
    session: Session,
    course_id: int,
    student_ids: list[int],
) -> dict[tuple[int, int], float]:
    """基于课程测试各题扣分计算学生-知识点掌握度（0-100）。

    数据来源：CourseTestDetail（教师上传「各题扣分情况」模板落库）。
    每题按满分 EXAM_QUESTION_FULL_SCORE 计，掌握度 = 该知识点累计
    可得分扣去累计扣分后的得分率；一格含多个知识点时均摊。
    只返回有扣分数据的 (student_id, point_id) 组合。
    """
    if not student_ids:
        return {}

    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_ids = [m.module_id for m in modules]
    if not module_ids:
        return {}

    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all()
    name_to_point = {p.point_name.strip(): p.point_id for p in points}
    if not name_to_point:
        return {}

    batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()
    if not batch_ids:
        return {}

    details = session.exec(
        select(CourseTestDetail).where(
            CourseTestDetail.exam_batch_id.in_(batch_ids),  # type: ignore[arg-type]
            CourseTestDetail.student_id.in_(student_ids),  # type: ignore[arg-type]
        )
    ).all()

    loss: dict[tuple[int, int], float] = {}
    chance: dict[tuple[int, int], float] = {}
    for detail in details:
        for qn in range(1, 6):
            try:
                deduction = float(getattr(detail, f"question{qn}_score") or 0)
            except (TypeError, ValueError):
                deduction = 0.0
            if deduction <= 0:
                continue
            names = split_knowledge_names(getattr(detail, f"question{qn}_knowledge"))
            point_ids = [name_to_point[n] for n in names if n in name_to_point]
            if not point_ids:
                continue
            per_deduction = deduction / len(point_ids)
            per_chance = EXAM_QUESTION_FULL_SCORE / len(point_ids)
            for point_id in point_ids:
                key = (detail.student_id, point_id)
                loss[key] = loss.get(key, 0.0) + per_deduction
                chance[key] = chance.get(key, 0.0) + per_chance

    return {
        key: round((ch - loss.get(key, 0.0)) / ch * 100.0, 1)
        for key, ch in chance.items()
        if ch > 0
    }


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

    point_ids = [p.point_id for p in points]

    # 一次聚合全部知识点的答题正确数/总数（避免逐知识点查询）
    answer_rows = session.exec(
        select(
            AiQuestion.point_id,
            func.count(StudentAnswerRecord.answer_id),
            func.sum(StudentAnswerRecord.is_correct),
        )
        .join(StudentAnswerRecord, StudentAnswerRecord.question_id == AiQuestion.question_id)
        .where(
            StudentAnswerRecord.student_id == student_id,
            AiQuestion.course_id == course_id,
            AiQuestion.point_id.in_(point_ids),  # type: ignore[arg-type]
        )
        .group_by(AiQuestion.point_id)
    ).all()
    answer_stats = {pid: (total, correct) for pid, total, correct in answer_rows}

    # 兜底：KnowledgeMastery 表一次取
    km_rows = session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.student_id == student_id,
            KnowledgeMastery.course_id == course_id,
            KnowledgeMastery.point_id.in_(point_ids),  # type: ignore[arg-type]
        )
    ).all()
    km_scores = {km.point_id: km.mastery_score for km in km_rows}

    # 考试扣分折算的掌握度（仅覆盖有扣分数据的知识点）
    exam_index = compute_exam_mastery_indexes(session, course_id, [student_id])

    results: list[MasteryStat] = []
    for p in points:
        total, correct = answer_stats.get(p.point_id, (0, 0))
        exam_score = exam_index.get((student_id, p.point_id))
        stored_score = km_scores.get(p.point_id)
        if not total and exam_score is None and stored_score is None:
            continue
        if total and total > 0:
            accuracy = (correct or 0) * 100.0 / total
            # 答题正确率与考试扣分并存时取平均
            if exam_score is not None:
                accuracy = round((accuracy + exam_score) / 2.0, 1)
        elif exam_score is not None:
            accuracy = exam_score
        else:
            accuracy = stored_score

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


def refresh_student_mastery(session: Session, student_id: int, course_id: int) -> int:
    """按该生全部答题记录 + 课程测试扣分刷新持久化个人掌握度。

    答题正确率与考试扣分折算值并存时取平均；
    仅考试扣分覆盖的知识点也写入（替代旧的成绩均值估算）。
    """
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
    answer_stats = {point_id: (total, correct) for point_id, total, correct in rows}

    exam_index = compute_exam_mastery_indexes(session, course_id, [student_id])

    point_ids = set(answer_stats.keys()) | {
        point_id for (sid, point_id) in exam_index if sid == student_id
    }
    existing_rows = session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.course_id == course_id,
            KnowledgeMastery.student_id == student_id,
        )
    ).all()
    existing_by_point = {row.point_id: row for row in existing_rows}

    for point_id in point_ids:
        total, correct = answer_stats.get(point_id, (0, 0))
        exam_score = exam_index.get((student_id, point_id))
        if total:
            score = round((correct or 0) * 100.0 / total, 1)
            if exam_score is not None:
                score = round((score + exam_score) / 2.0, 1)
        elif exam_score is not None:
            score = exam_score
        else:
            continue
        mastery = existing_by_point.get(point_id)
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
    session.flush()
    return len(point_ids)


def compute_mastery_index_with_fallback(
    session: Session,
    course_id: int,
    student_ids: list[int],
) -> dict[tuple[int, int], float]:
    """教师/管理员视角：优先答题记录，无记录时回退到 KnowledgeMastery 表。

    课程测试扣分折算的掌握度与答题正确率并存时取平均；
    其余无答题/无扣分数据的组合再回退 KnowledgeMastery 表，
    这样即使学生没有答题记录（如预注入的演示数据），教师也能看到
    知识点掌握度热力图，而不是全为 0。
    """
    answer_index = compute_assignment_accuracy_index(session, course_id, student_ids)

    # 考试扣分折算掌握度合并进索引（并存取平均）
    exam_index = compute_exam_mastery_indexes(session, course_id, student_ids)
    for pair, exam_score in exam_index.items():
        if pair in answer_index:
            answer_index[pair] = round((answer_index[pair] + exam_score) / 2.0, 1)
        else:
            answer_index[pair] = exam_score

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
    accuracy_index = compute_mastery_index_with_fallback(session, course_id, student_ids)

    results: list[MasteryStat] = []
    for p in points:
        accs = [
            accuracy_index[(sid, p.point_id)]
            for sid in student_ids
            if (sid, p.point_id) in accuracy_index
        ]
        if not accs:
            continue
        avg_acc = sum(accs) / len(accs)

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
