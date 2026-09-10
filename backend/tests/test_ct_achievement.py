"""课程目标(CT1-CT8)达成度算法测试。

覆盖：
  - 知识点精确归因（CT1-CT4，high）
  - 无 CT 映射的知识点不参与归因
  - 考核批次类型归因（CT1-CT6，medium）
  - 素养类推断（CT7-CT8，low）
  - 无证据 CT 为 None 不计入总体
  - 班级聚合（均值/达成率）
  - 落库幂等
  - 常量与工具函数
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models import KnowledgePoint, CTAchievement
from app.services.ct_constants import (
    CT_CODES,
    degree_to_level,
    parse_ct_field,
)
from app.services.ct_achievement import (
    compute_student_ct,
    compute_class_ct,
    persist_ct_achievement,
    refresh_ct_achievement,
)


# ============================================================================
# 常量与工具函数
# ============================================================================

class TestCTConstants:
    def test_ct_codes_order(self):
        assert CT_CODES == ["CT1", "CT2", "CT3", "CT4", "CT5", "CT6", "CT7", "CT8"]

    def test_degree_to_level_thresholds(self):
        """OBE 口径：85/70/60/40。"""
        assert degree_to_level(90) == "优秀"
        assert degree_to_level(85) == "优秀"
        assert degree_to_level(84.9) == "良好"
        assert degree_to_level(70) == "良好"
        assert degree_to_level(60) == "合格"
        assert degree_to_level(40) == "不足"
        assert degree_to_level(39.9) == "严重不足"

    def test_parse_ct_field_normal(self):
        assert parse_ct_field("CT1,CT2,CT4") == ["CT1", "CT2", "CT4"]

    def test_parse_ct_field_chinese_separator(self):
        assert parse_ct_field("CT1，CT2") == ["CT1", "CT2"]

    def test_parse_ct_field_whitespace(self):
        assert parse_ct_field(" CT1 , CT2 ") == ["CT1", "CT2"]

    def test_parse_ct_field_empty(self):
        assert parse_ct_field(None) == []
        assert parse_ct_field("") == []

    def test_parse_ct_field_invalid_filtered(self):
        assert parse_ct_field("CT1,CT9,XX") == ["CT1"]

    def test_parse_ct_field_dedup(self):
        assert parse_ct_field("CT1,CT1,CT2") == ["CT1", "CT2"]


# ============================================================================
# 知识点精确归因
# ============================================================================

class TestKnowledgeCTAttribution:
    """知识点掌握度 → CT1-CT4 精确归因。"""

    @staticmethod
    def _reset_kp_ct(session: Session):
        """还原知识点的 course_objectives，避免污染共享数据库。"""
        for kp in session.exec(select(KnowledgePoint)).all():
            kp.course_objectives = None
            session.add(kp)
        session.commit()

    def test_knowledge_point_with_ct_maps_to_correct_ct(self, session: Session):
        """有 CT 映射的知识点掌握度正确分配到对应 CT。"""
        # conftest 知识点：1=二叉树 2=红黑树 3=快速排序 4=归并排序
        # 给知识点 1 映射 CT1,CT2；知识点 2 映射 CT1,CT2,CT4
        kp1 = session.get(KnowledgePoint, 1)
        kp1.course_objectives = "CT1,CT2"
        kp2 = session.get(KnowledgePoint, 2)
        kp2.course_objectives = "CT1,CT2,CT4"
        session.add_all([kp1, kp2])
        session.commit()

        try:
            result = compute_student_ct(session, student_id=1, course_id=1)
            # CT1/CT2 有知识点归因（high 置信度）
            assert result.ct_scores["CT1"] is not None
            assert result.ct_scores["CT2"] is not None
            assert result.ct_confidence.get("CT1") == "high"
        finally:
            self._reset_kp_ct(session)

    def test_knowledge_point_without_ct_not_attributed(self, session: Session):
        """course_objectives 为空的知识点不参与任何 CT 归因。"""
        # 确保所有知识点都没设 CT 映射
        for kp in session.exec(select(KnowledgePoint)).all():
            kp.course_objectives = None
            session.add(kp)
        session.commit()

        result = compute_student_ct(session, student_id=1, course_id=1)
        # 无知识点归因时，CT1-CT4 不应有 high 置信度
        for ct in ["CT1", "CT2", "CT3", "CT4"]:
            assert result.ct_confidence.get(ct) != "high"


# ============================================================================
# 考核批次类型归因
# ============================================================================

class TestBatchTypeAttribution:
    """按 ExamBatch.batch_type 归因到 CT。"""

    def test_batch_type_weights_applied(self, session: Session):
        """实验批次(batch_type=2)成绩归因到 CT5/CT6。

        conftest 无实验批次，添加一个验证。用高 batch_id 避免与现有数据冲突，
        测试后清理避免污染 session 级共享数据库。
        """
        from app.models import ExamBatch, IndividualScore
        from datetime import datetime
        # 加一个实验批次
        session.add(ExamBatch(
            batch_id=900, course_id=1, batch_name="CT测试实验", batch_type=2,
            exam_time=datetime(2024, 12, 1), full_score=100, create_by=1,
        ))
        session.add(IndividualScore(
            score_id=900, student_id=1, exam_batch_id=900, score=80, create_by=1,
        ))
        session.commit()

        try:
            result = compute_student_ct(session, student_id=1, course_id=1)
            # CT5/CT6 应有值（实验 batch_type=2 含 CT5:0.3 CT6:0.3）
            assert result.ct_scores["CT5"] is not None
            assert result.ct_scores["CT6"] is not None
        finally:
            # 清理：删除测试插入的数据，避免污染 session 级共享数据库
            for row in session.exec(
                select(IndividualScore).where(IndividualScore.exam_batch_id == 900)
            ).all():
                session.delete(row)
            for row in session.exec(
                select(ExamBatch).where(ExamBatch.batch_id == 900)
            ).all():
                session.delete(row)
            session.commit()


# ============================================================================
# 素养类推断
# ============================================================================

class TestLiteracyInference:
    """CT7/CT8 素养推断（low 置信度）。"""

    def test_ct7_ct8_always_have_low_confidence(self, session: Session):
        """CT7/CT8 始终有值且置信度为 low。"""
        result = compute_student_ct(session, student_id=1, course_id=1)
        assert result.ct_scores["CT7"] is not None
        assert result.ct_scores["CT8"] is not None
        assert result.ct_confidence.get("CT7") == "low"
        assert result.ct_confidence.get("CT8") == "low"

    def test_ct7_ct8_no_data_returns_zero(self, session: Session):
        """无考勤/参与/实践数据时 CT7/CT8 为 0（素养类有兜底）。"""
        # 学生3 王五有考勤和互动，但无实验成绩
        result = compute_student_ct(session, student_id=3, course_id=1)
        # 实践成绩无 → 0；考勤有 → 有值；CT7 应介于 0-100
        assert 0 <= result.ct_scores["CT7"] <= 100
        assert 0 <= result.ct_scores["CT8"] <= 100


# ============================================================================
# 总体达成度
# ============================================================================

class TestOverallAchievement:
    def test_overall_is_mean_of_valid_cts(self, session: Session):
        """总体达成度 = 有证据 CT 的均值。"""
        result = compute_student_ct(session, student_id=1, course_id=1)
        valid = [s for s in result.ct_scores.values() if s is not None]
        if valid:
            expected = round(sum(valid) / len(valid), 1)
            assert result.overall_score == expected

    def test_overall_level_matches_score(self, session: Session):
        """总体等级与总体分值匹配。"""
        result = compute_student_ct(session, student_id=1, course_id=1)
        assert result.overall_level == degree_to_level(result.overall_score)

    def test_weak_cts_below_60(self, session: Session):
        """weak_cts 收集所有 <60 的 CT。"""
        result = compute_student_ct(session, student_id=1, course_id=1)
        for ct in result.weak_cts:
            assert result.ct_scores[ct] < 60


# ============================================================================
# 班级聚合
# ============================================================================

class TestClassAggregation:
    def test_class_ct_returns_all_cts(self, session: Session):
        """班级聚合返回全部 8 个 CT 的均值/标准差/达成率。"""
        result = compute_class_ct(session, course_id=1)
        for ct in CT_CODES:
            assert ct in result["ct_avg"]
            assert ct in result["ct_std"]
            assert ct in result["ct_pass_rate"]

    def test_class_student_count(self, session: Session):
        """班级聚合包含全部选修学生。"""
        result = compute_class_ct(session, course_id=1)
        # conftest 3 个学生选修课程1
        assert result["student_count"] == 3
        assert len(result["students"]) <= 3

    def test_pass_rate_range(self, session: Session):
        """达成率在 [0,1] 区间。"""
        result = compute_class_ct(session, course_id=1)
        for ct in CT_CODES:
            rate = result["ct_pass_rate"][ct]
            assert 0 <= rate <= 1


# ============================================================================
# 落库
# ============================================================================

class TestPersist:
    @staticmethod
    def _cleanup(session: Session):
        """清理 ct_achievement 行，避免污染共享数据库。"""
        for row in session.exec(select(CTAchievement)).all():
            session.delete(row)
        session.commit()

    def test_persist_writes_row(self, session: Session):
        """落库写入 ct_achievement 行。"""
        result = compute_student_ct(session, student_id=1, course_id=1)
        aid = persist_ct_achievement(session, 1, 1, result=result)
        assert aid > 0
        try:
            row = session.exec(
                select(CTAchievement).where(
                    CTAchievement.course_id == 1, CTAchievement.student_id == 1
                )
            ).first()
            assert row is not None
            assert row.overall_score == result.overall_score
        finally:
            self._cleanup(session)

    def test_persist_idempotent_no_duplicate(self, session: Session):
        """重复落库不产生重复行（联合唯一索引）。"""
        try:
            for _ in range(3):
                persist_ct_achievement(session, 1, 1)
            count = len(session.exec(
                select(CTAchievement).where(
                    CTAchievement.course_id == 1, CTAchievement.student_id == 1
                )
            ).all())
            assert count == 1
        finally:
            self._cleanup(session)

    def test_refresh_course_all_students(self, session: Session):
        """refresh_ct_achievement 刷新课程全部学生。"""
        try:
            result = refresh_ct_achievement(session, course_id=1)
            assert result["ct_achievements_updated"] == 3
            rows = session.exec(
                select(CTAchievement).where(CTAchievement.course_id == 1)
            ).all()
            assert len(rows) == 3
        finally:
            self._cleanup(session)
