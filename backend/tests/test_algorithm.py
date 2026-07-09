"""D01-D12 算法层单元测试。

覆盖：
    test_predict      D01 成绩预测 + D04 进步分
    test_profile      D02 学业水平 + D03 学习态度
    test_mastery      D05 知识点掌握度
    test_warning      D06/D07 预警
    test_tag          D09 学情标签
    test_evaluation   D08 综合评价
    test_dedup        D12 题目去重
    test_report       D10 报告模板
"""
from __future__ import annotations

import pytest


# ===== D01 成绩预测 =====

class TestPredict:
    def test_regression_basic(self):
        """一元线性回归基本逻辑。"""
        from app.services.predict import simple_linear_regression
        # 上升序列
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [60.0, 65.0, 70.0, 75.0, 80.0]
        reg = simple_linear_regression(xs, ys)
        assert reg.slope > 0
        assert reg.degraded is False
        assert reg.r_squared > 0.99  # 完美线性
        assert 84 <= reg.next_predict <= 86

    def test_regression_degraded(self):
        """数据不足时降级。"""
        from app.services.predict import simple_linear_regression
        reg = simple_linear_regression([1.0], [70.0])
        assert reg.degraded is True
        assert reg.next_predict == 70.0

    def test_predict_student(self, session):
        """完整学生成绩预测。"""
        from app.services.predict import predict_student_scores
        result = predict_student_scores(session, student_id=1, course_id=1)
        assert "current" in result
        assert "predicted" in result
        assert "trend" in result
        # 张三 85→75→55，应该是下滑
        assert result["trend"] == "下滑"
        assert result["current"] == 55.0
        assert result["degraded"] is False  # 3 个数据点

    def test_slope_to_progress(self):
        """D04 进步分映射。"""
        from app.services.predict import slope_to_progress_score
        # slope=0 → 50
        assert slope_to_progress_score(0.0) == 50.0
        # slope>0 → >50
        assert slope_to_progress_score(2.0) == 70.0
        # slope<0 → <50
        assert slope_to_progress_score(-2.0) == 30.0
        # 班级归一化
        score = slope_to_progress_score(1.0, class_slopes=[1.0, -1.0])
        assert 50 < score <= 100


# ===== D02/D03/D04 画像 =====

class TestProfile:
    def test_academic_score(self, session):
        """D02 学业水平（Z-score 标准化）。"""
        from app.services.profile import compute_academic_score
        score = compute_academic_score(session, student_id=1, course_id=1)
        assert 0 <= score <= 100
        # Z-score 测量相对位置（近期权重高），张三前两次高于均值
        # 结果应在合理范围内
        assert 60 <= score <= 85

    def test_attitude_score(self, session):
        """D03 学习态度。"""
        from app.services.profile import compute_attitude_score
        score, detail = compute_attitude_score(session, student_id=1, course_id=1)
        assert 0 <= score <= 100
        assert "attendance_rate" in detail
        # 张三缺勤 3/4 次，出勤率 25%
        assert detail["attendance_rate"] == 0.25

    def test_progress_score(self, session):
        """D04 学习进步。"""
        from app.services.profile import compute_progress_score
        # 王五（student_id=3）成绩上升 60→70→80
        score = compute_progress_score(session, student_id=3, course_id=1)
        assert score > 50  # 进步分为正

    def test_profile_summary(self, session):
        """三维度汇总。"""
        from app.services.profile import compute_profile
        p = compute_profile(session, student_id=2, course_id=1)
        assert 0 <= p.academic_score <= 100
        assert 0 <= p.attitude_score <= 100
        assert 0 <= p.progress_score <= 100


# ===== D05 掌握度 =====

class TestMastery:
    def test_accuracy_to_level(self):
        from app.services.mastery import accuracy_to_level
        assert accuracy_to_level(85) == ("良好", "green")
        assert accuracy_to_level(70) == ("一般", "yellow")
        assert accuracy_to_level(50) == ("薄弱", "red")

    def test_student_mastery(self, session):
        """学生知识点掌握度。"""
        from app.services.mastery import compute_student_mastery
        ms = compute_student_mastery(session, student_id=1, course_id=1)
        assert len(ms) > 0
        # 有答题记录的知识点应该有数据
        for m in ms:
            assert 0 <= m.accuracy <= 100
            assert m.level in ("良好", "一般", "薄弱")

    def test_class_mastery(self, session):
        """班级知识点掌握度。"""
        from app.services.mastery import compute_class_mastery
        ms = compute_class_mastery(session, course_id=1)
        assert len(ms) > 0


# ===== D06/D07 预警 =====

class TestWarning:
    def test_w1_score_drop(self, session):
        """W1 成绩下滑检测。"""
        from app.services.warning import evaluate_student
        result = evaluate_student(session, student_id=1, course_id=1)
        # 张三 75→55，下滑 20 分，应命中 W1
        rules = [h.rule for h in result.hits]
        assert "W1" in rules

    def test_w3_attendance(self, session):
        """W3 缺勤超标。"""
        from app.services.warning import evaluate_student
        result = evaluate_student(session, student_id=1, course_id=1)
        rules = [h.rule for h in result.hits]
        assert "W3" in rules  # 张三缺勤 3 次

    def test_level_resolution(self, session):
        """D07 等级判定。"""
        from app.services.warning import evaluate_student
        result = evaluate_student(session, student_id=1, course_id=1)
        # 张三命中多条规则，等级至少为"中"
        assert result.final_level in ("中", "高")
        assert result.level_code >= 2

    def test_no_false_positive(self, session):
        """李四稳定，不应触发预警。"""
        from app.services.warning import evaluate_student
        result = evaluate_student(session, student_id=2, course_id=1)
        # 李四成绩稳定 70→72→68，不应有 W1
        rules = [h.rule for h in result.hits]
        assert "W1" not in rules


# ===== D09 标签 =====

class TestTag:
    def test_tags_generated(self, session):
        """标签生成。"""
        from app.services.tag import generate_tags
        tags = generate_tags(session, student_id=1, course_id=1)
        assert len(tags) > 0
        # 张三应该有"下滑预警"
        assert "下滑预警" in tags

    def test_tags_stable(self, session):
        """李四稳定型标签。"""
        from app.services.tag import generate_tags
        tags = generate_tags(session, student_id=2, course_id=1)
        # 李四可能稳定也可能待观察
        assert len(tags) > 0

    def test_tags_progress(self, session):
        """王五进步标签。"""
        from app.services.tag import generate_tags
        tags = generate_tags(session, student_id=3, course_id=1)
        assert "进步显著" in tags


# ===== D08 综合评价 =====

class TestEvaluation:
    def test_score_to_level(self):
        from app.services.evaluation import score_to_level
        assert score_to_level(90) == "优"
        assert score_to_level(80) == "良"
        assert score_to_level(65) == "中"
        assert score_to_level(50) == "差"

    def test_compute_evaluation(self, session):
        """综合评价。"""
        from app.services.evaluation import compute_evaluation
        result = compute_evaluation(session, student_id=2, course_id=1)
        assert 0 <= result.total_score <= 100
        assert result.level in ("优", "良", "中", "差")
        assert "academic" in result.dimensions
        assert "attitude" in result.dimensions
        assert "mastery" in result.dimensions


# ===== D12 去重 =====

class TestDedup:
    def test_cosine_identical(self):
        """相同题目相似度应接近 1。"""
        from app.services.dedup import check_duplicate_against_bank
        q = {"content": "红黑树的性质是什么", "options": ["A.x", "B.y"], "correct_answer": "A"}
        bank = [{"content": "红黑树的性质是什么", "options": ["A.x", "B.y"], "correct_answer": "A"}]
        is_dup, sim, _ = check_duplicate_against_bank(q, bank)
        assert is_dup is True
        assert sim > 0.9

    def test_cosine_different(self):
        """不同题目不应判重。"""
        from app.services.dedup import check_duplicate_against_bank
        q = {"content": "快速排序的时间复杂度", "options": [], "correct_answer": "Onlogn"}
        bank = [{"content": "红黑树的旋转操作", "options": [], "correct_answer": "左旋"}]
        is_dup, sim, _ = check_duplicate_against_bank(q, bank)
        assert is_dup is False
        assert sim < 0.5

    def test_dedup_batch(self):
        """批量去重。"""
        from app.services.dedup import dedup_questions
        qs = [
            {"content": "二叉树的前序遍历", "options": ["A"], "correct_answer": "A"},
            {"content": "二叉树的前序遍历", "options": ["A"], "correct_answer": "A"},  # 重复
            {"content": "快速排序的原理", "options": ["B"], "correct_answer": "B"},
        ]
        result = dedup_questions(qs, threshold=0.8)
        assert len(result.kept) == 2
        assert len(result.duplicates) == 1


# ===== D10 报告模板 =====

class TestReport:
    def test_class_report(self, session):
        """班级报告模板。"""
        from app.services.report_template import build_class_context, render_report
        ctx = build_class_context(session, course_id=1)
        report = render_report(ctx)
        assert report["scope"] == "class"
        assert "summary" in report
        assert "conclusion" in report
        assert "suggestion" in report
        assert len(report["summary"]) > 10

    def test_student_report(self, session):
        """学生报告模板。"""
        from app.services.report_template import build_student_context, render_report
        ctx = build_student_context(session, student_id=1, course_id=1)
        report = render_report(ctx)
        assert report["scope"] == "student"
        assert "张三" in report["summary"]
