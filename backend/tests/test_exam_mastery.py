"""课程测试各题扣分 → 知识点掌握度 测试。

覆盖：
- 复合知识点名称拆分规则
- 扣分折算掌握度（每题按 20 分计，多知识点均摊）
- 答题正确率与考试扣分并存时取平均
- 热力图/失分率按拆分后知识点归属
- 历史复合知识点拆分迁移（幂等）
"""
from datetime import datetime

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session as SqlSession, create_engine, select

from app.api.v1.analysis import get_knowledge_heatmap
from app.core import database
from app.models import (
    AiQuestion,
    Course,
    CourseTestDetail,
    KnowledgeMastery,
    KnowledgeModule,
    KnowledgePoint,
    StudentAnswerRecord,
    SysUser,
)
from app.services.knowledge_utils import split_knowledge_names
from app.services.mastery import (
    compute_exam_mastery_indexes,
    compute_student_mastery,
    refresh_student_mastery,
)


# ============================================================================
# 名称拆分
# ============================================================================

def test_split_knowledge_names():
    assert split_knowledge_names("传输时延、TCP/UDP协议") == ["传输时延", "TCP/UDP协议"]
    assert split_knowledge_names("ARP协议") == ["ARP协议"]
    assert split_knowledge_names(" 传输时延 、TCP/IP参考模型") == ["传输时延", "TCP/IP参考模型"]
    assert split_knowledge_names("A，B；C") == ["A", "B", "C"]
    assert split_knowledge_names("传输时延、、TCP协议") == ["传输时延", "TCP协议"]
    # 斜杠不能作为分隔符（TCP/IP 名称本身含斜杠）
    assert split_knowledge_names("TCP/IP参考模型") == ["TCP/IP参考模型"]
    assert split_knowledge_names("") == []
    assert split_knowledge_names(None) == []


# ============================================================================
# 扣分折算掌握度
# ============================================================================

def test_exam_mastery_from_deductions(session):
    """每题按 20 分计；一格多知识点均摊扣分与可得分。"""
    session.add(CourseTestDetail(
        score_id=201,
        student_id=2,
        exam_batch_id=3,
        question1_score=4,
        question1_knowledge="二叉树、红黑树",
        question2_score=6,
        question2_knowledge="快速排序",
        total_score=90,
        create_by=1,
    ))
    session.flush()

    result = compute_exam_mastery_indexes(session, course_id=1, student_ids=[1, 2])
    # 二叉树：可得分 10、扣分 2 → 80；红黑树同理；快速排序：(20-6)/20 → 70
    assert result == {(2, 1): 80.0, (2, 2): 80.0, (2, 3): 70.0}


def test_exam_mastery_ignores_blank_and_unmatched_names(session):
    """无扣分或无知识点名称的题不计；未匹配的名称跳过。"""
    session.add(CourseTestDetail(
        score_id=202,
        student_id=2,
        exam_batch_id=3,
        question1_score=0,
        question1_knowledge="二叉树",
        question2_score=3,
        question2_knowledge=None,
        question3_score=2,
        question3_knowledge="不存在的知识点",
        total_score=95,
        create_by=1,
    ))
    session.flush()

    assert compute_exam_mastery_indexes(session, course_id=1, student_ids=[2]) == {}


# ============================================================================
# 与答题正确率合并（取平均）
# ============================================================================

def _make_unique_point(session, name: str, module_id: int = 1) -> KnowledgePoint:
    point = KnowledgePoint(module_id=module_id, point_name=name, sort_num=0)
    session.add(point)
    session.flush()
    return point


def test_mastery_merge_average_and_refresh(session):
    """答题正确率 100 + 考试折算 80 → 平均 90 落库；仅考试覆盖的点也写入。"""
    point = _make_unique_point(session, f"合并测试-{datetime.now().timestamp()}")
    question = AiQuestion(
        course_id=1, point_id=point.point_id, type=1,
        content="merge-test", correct_answer="A", create_by=1,
    )
    session.add(question)
    session.flush()
    session.add(StudentAnswerRecord(
        task_id=1, question_id=question.question_id, student_id=1,
        user_answer="A", score=100, is_correct=1,
    ))
    session.add(CourseTestDetail(
        score_id=203,
        student_id=1,
        exam_batch_id=3,
        question1_score=4,
        question1_knowledge=point.point_name,
        total_score=96,
        create_by=1,
    ))
    session.flush()

    refresh_student_mastery(session, student_id=1, course_id=1)
    session.flush()

    km = session.exec(select(KnowledgeMastery).where(
        KnowledgeMastery.course_id == 1,
        KnowledgeMastery.student_id == 1,
        KnowledgeMastery.point_id == point.point_id,
    )).one()
    # 答题 100 与考试折算 80 取平均
    assert km.mastery_score == 90.0
    assert km.mastery_level == 3

    stats = {
        s.point_id: s.accuracy
        for s in compute_student_mastery(session, student_id=1, course_id=1)
    }
    assert stats[point.point_id] == 90.0


def test_mastery_exam_only_point_written(session):
    """无答题记录、仅有考试扣分的知识点也写入掌握度。"""
    point = _make_unique_point(session, f"仅考试-{datetime.now().timestamp()}")
    session.add(CourseTestDetail(
        score_id=204,
        student_id=3,
        exam_batch_id=3,
        question1_score=9,
        question1_knowledge=point.point_name,
        total_score=91,
        create_by=1,
    ))
    session.flush()

    refresh_student_mastery(session, student_id=3, course_id=1)
    session.flush()

    km = session.exec(select(KnowledgeMastery).where(
        KnowledgeMastery.course_id == 1,
        KnowledgeMastery.student_id == 3,
        KnowledgeMastery.point_id == point.point_id,
    )).one()
    # (20-9)/20 → 55
    assert km.mastery_score == 55.0
    assert km.mastery_level == 1


# ============================================================================
# 热力图与失分率
# ============================================================================

def test_heatmap_includes_exam_mastery(session):
    """教师视角热力图直接呈现考试扣分折算的掌握度。"""
    point = _make_unique_point(session, f"热力图-{datetime.now().timestamp()}")
    session.add(CourseTestDetail(
        score_id=205,
        student_id=3,
        exam_batch_id=3,
        question1_score=4,
        question1_knowledge=point.point_name,
        total_score=96,
        create_by=1,
    ))
    session.flush()

    result = get_knowledge_heatmap(
        course_id=1,
        class_id=1,
        student_id=None,
        session=session,
        current_user=session.get(SysUser, 1),
    )
    kp_idx = result["knowledgePoints"].index(point.point_name)
    student_idx = result["students"].index("王五")
    row = next(r for r in result["data"] if r[:2] == [kp_idx, student_idx])
    assert row[2] == 80.0


def test_loss_rate_splits_multi_knowledge_cell(session):
    """失分率统计同样按拆分后的知识点均摊扣分。"""
    session.add(CourseTestDetail(
        score_id=206,
        student_id=1,
        exam_batch_id=3,
        question1_score=4,
        question1_knowledge="二叉树、红黑树",
        total_score=96,
        create_by=1,
    ))
    session.flush()

    result = get_knowledge_heatmap(
        course_id=1,
        class_id=1,
        student_id=1,
        session=session,
        current_user=session.get(SysUser, 1),
    )
    assert result["lossRateByKp"][:2] == [2.0, 2.0]


# ============================================================================
# 历史复合知识点拆分迁移
# ============================================================================

def test_migrate_split_combined_knowledge_points_is_idempotent(monkeypatch):
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with SqlSession(eng) as s:
        s.add(Course(course_id=1, course_code="CS101", course_name="计算机网络",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院"))
        s.add(KnowledgeModule(module_id=1, course_id=1, module_name="默认模块"))
        s.add(KnowledgeModule(module_id=2, course_id=1, module_name="其他模块"))
        # 复合知识点 + 已存在的拆分片段（应复用而非新建）
        s.add(KnowledgePoint(point_id=1, module_id=1, point_name="传输时延、TCP/UDP协议"))
        s.add(KnowledgePoint(point_id=2, module_id=2, point_name="TCP/UDP协议"))
        s.add(KnowledgeMastery(course_id=1, student_id=9, point_id=1,
                               mastery_score=50, mastery_level=1))
        s.add(AiQuestion(question_id=1, course_id=1, point_id=1, type=1,
                         content="q?", correct_answer="A", create_by=1))
        s.commit()

    monkeypatch.setattr(database, "engine", eng)
    database._migrate_split_combined_knowledge_points()
    database._migrate_split_combined_knowledge_points()  # 幂等：第二次无复合点可拆

    with SqlSession(eng) as s:
        points = {p.point_name: p for p in s.exec(select(KnowledgePoint)).all()}
        assert "传输时延、TCP/UDP协议" not in points
        assert "传输时延" in points
        assert points["传输时延"].module_id == 1
        # 已存在的同名片段复用（仅一条 TCP/UDP协议，仍在模块 2）
        assert points["TCP/UDP协议"].point_id == 2
        # 复合点的掌握度记录已清理
        assert not s.exec(select(KnowledgeMastery).where(
            KnowledgeMastery.point_id == 1
        )).all()
        # 引用复合点的题目改挂到第一个拆分片段
        question = s.get(AiQuestion, 1)
        assert question.point_id == points["传输时延"].point_id
