"""AI 学情诊断 Agent 单元测试（diagnosis）。

覆盖（对应 docs/算法设计/AI学情分析_开发文档_v1.0.md §5）：
    L1 工具单测（8 例）：直接调 queries.py 的 _t_xxx，验证返回结构与种子数据
    L2 FC 循环集成（9 例）：MockLLMProxy 脚本化驱动 diagnosis Agent，验证工具编排与 JSON 输出

种子数据（conftest.py）：
    张三(1, 85→75→55 下滑, 红黑树 mastery=30, 1 条 level-2 预警)
    李四(2, 70→72→68 稳定)
    王五(3, 60→70→80 进步)
    4 知识点：二叉树/红黑树/快速排序/归并排序
"""
from __future__ import annotations

import json

import pytest
from sqlmodel import Session

from app.services.agent.llm_proxy import (
    FCResult,
    LLMProxy,
    MockLLMProxy,
    set_llm_proxy,
)
from app.services.agent.registry import ToolContext, get_registry
from app.services.agent.tools import register_all_tools


@pytest.fixture(autouse=True)
def _setup_tools():
    """每个测试前确保工具已注册。"""
    register_all_tools()


def _ctx(session: Session, **kw) -> ToolContext:
    return ToolContext(session=session, user_id=1, course_id=1, **kw)


# ============================================================
# L1 工具单测
# ============================================================

class TestDiagnosisTools:
    """学情查询工具 L1 单测（直接调 _t_xxx，绕过 LLM）。"""

    def test_get_course_overview(self, session):
        """课程总览返回学生数/均分/及格率/出勤率/预警数。"""
        from app.services.agent.tools.queries import _t_get_course_overview

        result = _t_get_course_overview(_ctx(session), course_id=1)
        assert result["course_name"] == "数据结构"
        assert result["student_count"] == 3
        assert result["avg_score"] > 0          # 最近一次（期中）均分
        assert result["warning_count"] >= 1     # 张三有 1 条预警
        assert "pass_rate" in result
        assert "attendance_rate" in result

    def test_course_overview_skips_scoreless_latest_batch(self, session):
        """考勤等无成绩批次不能把课程总览成绩覆盖成 0。"""
        from datetime import datetime

        from app.models import ExamBatch
        from app.services.agent.tools.queries import _t_get_course_overview

        scoreless_batch = ExamBatch(
            course_id=1,
            batch_name="数据结构-考勤情况",
            batch_type=5,
            batch_weight=0,
            semester="2024-2025-1",
            exam_time=datetime(2025, 1, 10),
            full_score=100,
            create_by=1,
            create_time=datetime(2030, 1, 1),
        )
        session.add(scoreless_batch)
        session.commit()

        result = _t_get_course_overview(_ctx(session), course_id=1)
        assert result["avg_score"] == pytest.approx(67.7, abs=0.1)
        assert result["pass_rate"] == pytest.approx(66.7, abs=0.1)
        session.delete(scoreless_batch)
        session.commit()

    def test_course_overview_reads_attendance_sheet(self, session):
        """课程总览应读取当前数据管理模块使用的新考勤表。"""
        from app.models import AttendanceSheet
        from app.services.agent.tools.queries import _t_get_course_overview

        sheet = AttendanceSheet(
            student_id=1,
            exam_batch_id=1,
            total_count=4,
            present_count=3,
            attendance_rate=0.75,
            create_by=1,
        )
        session.add(sheet)
        session.commit()

        try:
            result = _t_get_course_overview(_ctx(session), course_id=1)
            assert result["attendance_rate"] == pytest.approx(58.3, abs=0.1)
        finally:
            session.delete(sheet)
            session.commit()

    def test_get_weak_knowledge_points(self, session):
        """薄弱知识点 TopK：红黑树 mastery=30 应排前列。"""
        from app.services.agent.tools.queries import _t_get_weak_knowledge_points

        result = _t_get_weak_knowledge_points(_ctx(session), course_id=1, top_k=5)
        assert "weak_points" in result
        assert len(result["weak_points"]) > 0
        point_names = [p["point_name"] for p in result["weak_points"]]
        assert "红黑树" in point_names
        # 按 accuracy 升序
        accuracies = [p["accuracy"] for p in result["weak_points"]]
        assert accuracies == sorted(accuracies)

    def test_get_score_trend_class(self, session):
        """班级成绩趋势：3 次考核，每次都有 avg_score。"""
        from app.services.agent.tools.queries import _t_get_score_trend

        result = _t_get_score_trend(_ctx(session), course_id=1, student_id=0)
        assert result["scope"] == "class"
        assert len(result["trend"]) == 3        # 作业1/作业2/期中
        assert all("avg_score" in t for t in result["trend"])

    def test_get_score_trend_zhangsan(self, session):
        """张三个人成绩趋势：85→75→55 下滑。"""
        from app.services.agent.tools.queries import _t_get_score_trend

        result = _t_get_score_trend(_ctx(session), course_id=1, student_id=1)
        assert result["scope"] == "student"
        assert result["student_id"] == 1
        scores = [t["score"] for t in result["trend"]]
        assert scores == [85.0, 75.0, 55.0]
        assert scores[0] > scores[-1]           # 下滑

    def test_get_warning_students(self, session):
        """预警学生列表：张三在列，level=中（warning_level=2）。"""
        from app.services.agent.tools.queries import _t_get_warning_students

        result = _t_get_warning_students(_ctx(session), course_id=1)
        assert "warning_students" in result
        assert len(result["warning_students"]) >= 1
        zhangsan = [w for w in result["warning_students"] if w["student_id"] == 1]
        assert len(zhangsan) == 1
        assert zhangsan[0]["level"] == "中"
        assert any("下滑" in r for r in zhangsan[0]["reasons"])

    def test_get_student_detail(self, session):
        """张三综合档案：成绩历史/考勤/掌握度字段齐全。"""
        from app.services.agent.tools.queries import _t_get_student_detail

        result = _t_get_student_detail(_ctx(session), course_id=1, student_id=1)
        assert result["name"] == "张三"
        assert len(result["scores"]) == 3       # 3 次考核
        # weak/strong 来自 compute_student_mastery（基于答题 accuracy），张三答对红黑树题 → strong
        assert "weak_points" in result
        assert "strong_points" in result
        assert result["attendance_rate"] is not None
        # 成绩下滑 85→75→55
        scores = [s["score"] for s in result["scores"]]
        assert scores == [85.0, 75.0, 55.0]

    def test_get_knowledge_mastery_class(self, session):
        """班级知识点掌握度：4 个知识点都有 accuracy 和 level。"""
        from app.services.agent.tools.queries import _t_get_knowledge_mastery

        result = _t_get_knowledge_mastery(_ctx(session), course_id=1, student_id=0)
        assert result["scope"] == "class"
        assert len(result["points"]) == 4
        assert all("accuracy" in p and "level" in p for p in result["points"])
        assert all(p["accuracy"] > 0 for p in result["points"])

    def test_tool_failure_fallback(self, session):
        """工具参数错误时返回 error dict，不抛异常（SAFE-03）。"""
        from app.services.agent.tools.queries import (
            _t_get_course_overview,
            _t_get_student_detail,
        )

        # 缺 student_id（student_id=0 视为未传）→ 返回 error
        result = _t_get_student_detail(_ctx(session), course_id=1, student_id=0)
        assert "error" in result
        # 不存在的课程
        result2 = _t_get_course_overview(_ctx(session), course_id=99999)
        assert "error" in result2


# ============================================================
# L2 FC 循环集成测试（Mock LLM）
# ============================================================

# 合法诊断 JSON 模板（班级版，6 顶层字段齐全）
_CLASS_DIAG_JSON = json.dumps(
    {
        "scope": "class",
        "overall": {"grade": "C", "score": 71, "summary": "班级均分下滑"},
        "findings": {
            "strengths": [],
            "risks": [
                {
                    "level": "中",
                    "subject": "成绩下滑",
                    "evidence": "期中均分下降",
                    "students": ["张三"],
                }
            ],
        },
        "causes": [],
        "suggestions": [],
        "radar": {"成绩": 71, "考勤": 75, "互动": 85, "进步": 60, "综合": 71},
        "meta": {
            "source": "llm",
            "toolsUsed": [
                "get_course_overview",
                "get_score_trend",
                "get_weak_knowledge_points",
                "get_warning_students",
            ],
        },
    },
    ensure_ascii=False,
)

# 降级诊断 JSON（数据不完整）
_DEGRADED_DIAG_JSON = json.dumps(
    {
        "scope": "class",
        "overall": {"grade": "-", "score": 0, "summary": "数据不完整"},
        "findings": {"strengths": [], "risks": []},
        "causes": [],
        "suggestions": [],
        "radar": {"成绩": 0, "考勤": 0, "互动": 0, "进步": 0, "综合": 0},
        "meta": {"source": "llm", "toolsUsed": []},
    },
    ensure_ascii=False,
)


class TestDiagnosisAgentFCLoop:
    """Mock LLM 驱动 diagnosis Agent 完整流程。"""

    def test_class_diagnosis_tool_sequence(self, session, engine):
        """FC-01 班级诊断：按 prompt 编排顺序调用基础四件套。"""
        from app.services.agent.base import run_agent

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_course_overview", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content="", tool_calls=[
                {"id": "c2", "name": "get_score_trend",
                 "arguments": {"course_id": 1, "student_id": 0}},
            ], finish_reason="tool_calls"),
            FCResult(content="", tool_calls=[
                {"id": "c3", "name": "get_weak_knowledge_points", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content="", tool_calls=[
                {"id": "c4", "name": "get_warning_students", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content=_CLASS_DIAG_JSON, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="诊断一下数据结构这门课的班级学情",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=8,
        )
        tool_names = [tc.name for s in result.steps for tc in s.tool_calls]
        assert "get_course_overview" in tool_names     # 总览先行
        assert tool_names[0] == "get_course_overview"
        assert "get_score_trend" in tool_names
        assert "get_weak_knowledge_points" in tool_names
        assert "get_warning_students" in tool_names
        assert result.error is None
        diag = json.loads(result.answer)
        assert diag["scope"] == "class"

    def test_student_diagnosis_calls_detail(self, session, engine):
        """FC-02 学生诊断：必须调 get_student_detail。"""
        from app.services.agent.base import run_agent

        student_diag = json.dumps({
            "scope": "student",
            "overall": {"grade": "D", "score": 55, "summary": "张三成绩下滑"},
            "findings": {"strengths": [], "risks": [
                {"level": "中", "subject": "成绩下滑", "evidence": "85→75→55", "students": ["张三"]}
            ]},
            "causes": [],
            "suggestions": [
                {"action": "针对红黑树补练", "priority": "高", "toolHint": "weakness_driven_quiz",
                 "target": "张三", "knowledgePoints": ["红黑树"]}
            ],
            "radar": {"成绩": 55, "考勤": 25, "互动": 85, "进步": 40, "综合": 55},
            "meta": {"source": "llm", "toolsUsed": ["get_student_detail"]},
            "studentInfo": {"name": "张三", "studentNo": "2024001", "studentId": 1},
            "scoreHistory": [
                {"assessment": "作业1", "score": 85},
                {"assessment": "作业2", "score": 75},
                {"assessment": "期中", "score": 55},
            ],
            "attitudeDetail": {"attendanceRate": 25, "weakPoints": ["红黑树"], "strongPoints": []},
        }, ensure_ascii=False)

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_student_detail",
                 "arguments": {"course_id": 1, "student_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content=student_diag, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="诊断张三的学情",
            user_id=1, course_id=1, student_id=1, agent_type="diagnosis", max_steps=5,
        )
        assert result.steps[0].tool_calls[0].name == "get_student_detail"
        assert result.steps[0].tool_calls[0].arguments["student_id"] == 1
        diag = json.loads(result.answer)
        assert diag["scope"] == "student"
        assert diag["studentInfo"]["name"] == "张三"

    def test_json_structure_complete(self, session, engine):
        """FC-03 输出 JSON 结构完整：6 顶层 key 齐全。"""
        from app.services.agent.base import run_agent

        complete_json = json.dumps({
            "scope": "class",
            "overall": {"grade": "B", "score": 78, "summary": "概述"},
            "findings": {"strengths": [], "risks": []},
            "causes": [],
            "suggestions": [],
            "radar": {"成绩": 78, "考勤": 90, "互动": 85, "进步": 70, "综合": 78},
            "meta": {"source": "llm", "toolsUsed": ["get_course_overview"]},
        }, ensure_ascii=False)

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_course_overview", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content=complete_json, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="简要诊断班级",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        )
        diag = json.loads(result.answer)
        for key in ["scope", "overall", "findings", "causes", "suggestions", "radar", "meta"]:
            assert key in diag, f"缺少顶层 key: {key}"
        assert "grade" in diag["overall"]
        assert "score" in diag["overall"]
        assert "summary" in diag["overall"]
        assert "strengths" in diag["findings"]
        assert "risks" in diag["findings"]
        assert "toolsUsed" in diag["meta"]

    def test_weak_point_identification(self, session, engine):
        """FC-04 薄弱点识别：红黑树 mastery=30 应出现在 risks/causes。"""
        from app.services.agent.base import run_agent

        weak_diag = json.dumps({
            "scope": "class",
            "overall": {"grade": "C", "score": 60, "summary": "红黑树掌握度极低"},
            "findings": {"strengths": [], "risks": [
                {"level": "高", "subject": "知识点薄弱", "evidence": "红黑树正确率30%",
                 "students": ["张三"]}
            ]},
            "causes": [
                {"issue": "红黑树掌握度低", "rootCause": "练习不足",
                 "dataRef": "get_weak_knowledge_points"}
            ],
            "suggestions": [
                {"action": "补充红黑树练习", "priority": "高", "toolHint": "weakness_driven_quiz",
                 "target": "班级", "knowledgePoints": ["红黑树"]}
            ],
            "radar": {"成绩": 60, "考勤": 75, "互动": 85, "进步": 60, "综合": 60},
            "meta": {"source": "llm", "toolsUsed": ["get_weak_knowledge_points"]},
        }, ensure_ascii=False)

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_weak_knowledge_points",
                 "arguments": {"course_id": 1, "top_k": 5}},
            ], finish_reason="tool_calls"),
            FCResult(content=weak_diag, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="班里哪个知识点最差",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        )
        # 工具返回的真实数据验证
        weak_result = result.steps[0].tool_calls[0].result
        assert "weak_points" in weak_result
        point_names = [p["point_name"] for p in weak_result["weak_points"]]
        assert "红黑树" in point_names
        # LLM 输出验证
        diag = json.loads(result.answer)
        risk_subjects = [r["subject"] for r in diag["findings"]["risks"]]
        assert any("知识点" in s or "薄弱" in s for s in risk_subjects)

    def test_decline_identification(self, session, engine):
        """FC-05 下滑识别：张三 85→75→55 应被识别为 risk。"""
        from app.services.agent.base import run_agent

        decline_diag = json.dumps({
            "scope": "student",
            "overall": {"grade": "D", "score": 55, "summary": "张三成绩持续下滑"},
            "findings": {"strengths": [], "risks": [
                {"level": "中", "subject": "成绩下滑", "evidence": "85→75→55", "students": ["张三"]}
            ]},
            "causes": [],
            "suggestions": [
                {"action": "约谈张三", "priority": "高", "toolHint": "talk",
                 "target": "张三", "knowledgePoints": []}
            ],
            "radar": {"成绩": 55, "考勤": 25, "互动": 85, "进步": 40, "综合": 55},
            "meta": {"source": "llm", "toolsUsed": ["get_score_trend"]},
            "studentInfo": {"name": "张三", "studentNo": "2024001", "studentId": 1},
            "scoreHistory": [
                {"assessment": "作业1", "score": 85},
                {"assessment": "作业2", "score": 75},
                {"assessment": "期中", "score": 55},
            ],
            "attitudeDetail": {"attendanceRate": 25, "weakPoints": [], "strongPoints": []},
        }, ensure_ascii=False)

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_score_trend",
                 "arguments": {"course_id": 1, "student_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content=decline_diag, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="张三成绩怎么样",
            user_id=1, course_id=1, student_id=1, agent_type="diagnosis", max_steps=3,
        )
        # 工具返回的真实趋势
        trend_result = result.steps[0].tool_calls[0].result
        scores = [t["score"] for t in trend_result["trend"]]
        assert scores == [85.0, 75.0, 55.0]
        assert scores[0] > scores[-1]       # 下滑
        # LLM 识别
        diag = json.loads(result.answer)
        assert any(
            "下滑" in r.get("subject", "") or "下滑" in r.get("evidence", "")
            for r in diag["findings"]["risks"]
        )

    def test_stable_excellent_no_false_alarm(self, session, engine):
        """FC-06 稳定优秀无误报：王五 60→70→80 进步，risks 应为空。"""
        from app.services.agent.base import run_agent

        progress_diag = json.dumps({
            "scope": "student",
            "overall": {"grade": "B", "score": 80, "summary": "王五稳步上升"},
            "findings": {"strengths": [
                {"point": "成绩进步", "value": "60→70→80", "evidence": "get_score_trend"}
            ], "risks": []},
            "causes": [],
            "suggestions": [],
            "radar": {"成绩": 80, "考勤": 100, "互动": 70, "进步": 90, "综合": 80},
            "meta": {"source": "llm", "toolsUsed": ["get_score_trend"]},
            "studentInfo": {"name": "王五", "studentNo": "2024003", "studentId": 3},
            "scoreHistory": [
                {"assessment": "作业1", "score": 60},
                {"assessment": "作业2", "score": 70},
                {"assessment": "期中", "score": 80},
            ],
            "attitudeDetail": {"attendanceRate": 100, "weakPoints": [], "strongPoints": []},
        }, ensure_ascii=False)

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_score_trend",
                 "arguments": {"course_id": 1, "student_id": 3}},
            ], finish_reason="tool_calls"),
            FCResult(content=progress_diag, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="王五表现怎么样",
            user_id=1, course_id=1, student_id=3, agent_type="diagnosis", max_steps=3,
        )
        trend_result = result.steps[0].tool_calls[0].result
        scores = [t["score"] for t in trend_result["trend"]]
        assert scores == [60.0, 70.0, 80.0]
        assert scores[0] < scores[-1]       # 进步
        diag = json.loads(result.answer)
        assert len(diag["findings"]["risks"]) == 0          # 进步学生无误报
        assert len(diag["findings"]["strengths"]) > 0

    def test_truncated_on_max_steps(self, session, engine):
        """FC-07 步数超限 truncated=True，不崩。"""
        from app.services.agent.base import run_agent

        # 每步都调工具，永不输出 content，强制耗尽 max_steps
        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": f"c{i}", "name": "get_course_overview", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls")
            for i in range(5)                # 5 步全调工具
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="诊断班级",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,   # 只给 3 步
        )
        assert result.truncated is True
        assert result.error is None
        assert len(result.steps) == 3

    def test_single_tool_failure_no_block(self, session, engine):
        """FC-08 单工具失败不阻断：LLM 收到 error 后继续输出降级 JSON。"""
        from app.services.agent.base import run_agent

        mock = MockLLMProxy([
            # Step 1: 调一个不存在的工具 → registry 返回 error
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "nonexistent_tool", "arguments": {}},
            ], finish_reason="tool_calls"),
            # Step 2: LLM 收到 error 后正常输出降级 JSON
            FCResult(content=_DEGRADED_DIAG_JSON, tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="诊断班级",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        )
        assert result.error is None                          # 工具失败但循环不崩
        # 不存在的工具：registry.execute 不抛异常，返回 {"error": ...} 作为 result
        tool_result = result.steps[0].tool_calls[0].result
        assert "error" in tool_result
        diag = json.loads(result.answer)
        assert diag["overall"]["summary"] == "数据不完整"

    def test_llm_failure_fallback(self, session, engine):
        """FC-09 LLM 失败兜底：FailingProxy 抛 RuntimeError，run_agent 不崩、error 非空。"""
        from app.services.agent.base import run_agent

        class FailingProxy(LLMProxy):
            def chat_with_tools(self, messages, tools, tool_choice="auto"):
                raise RuntimeError("LLM 服务不可用")

        set_llm_proxy(FailingProxy())

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf, user_message="诊断班级学情",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        )
        # 不崩 + error 非空 + answer 包含降级文案
        assert result.error is not None
        assert "不可用" in result.error or "困难" in result.error
        assert "不可用" in result.answer or "困难" in result.answer
        assert result.truncated is False


# ============================================================
# 导出适配函数单测
# ============================================================

class TestDiagnosisExportAdapter:
    """_diagnosis_to_report_fields 适配函数测试（TC-DIAG-EXPORT-04 兜底）。"""

    def test_full_diagnosis_to_report_fields(self):
        """完整诊断 JSON → 三段式字段齐全。"""
        from app.api.v1.report import _diagnosis_to_report_fields

        diag = {
            "overall": {"summary": "班级整体下滑"},
            "findings": {
                "strengths": [{"point": "出勤稳定", "value": "96%"}],
                "risks": [{"level": "高", "subject": "图论薄弱", "evidence": "42%",
                           "students": ["张三", "李四"]}],
            },
            "causes": [{"issue": "图论薄弱", "rootCause": "练习不足", "dataRef": "get_weak_knowledge_points"}],
            "suggestions": [{"action": "图论专项", "priority": "高", "toolHint": "weakness_driven_quiz",
                             "target": "全班", "knowledgePoints": ["图论"]}],
        }
        fields = _diagnosis_to_report_fields(diag)
        assert fields["summary"] == "班级整体下滑"
        assert "出勤稳定" in fields["conclusion"]
        assert "图论薄弱" in fields["conclusion"]
        assert "练习不足" in fields["conclusion"]
        assert "图论专项" in fields["suggestion"]
        assert "weakness_driven_quiz" in fields["suggestion"]

    def test_empty_diagnosis_to_report_fields(self):
        """空诊断 JSON → 三段式字段用 "-" 兜底。"""
        from app.api.v1.report import _diagnosis_to_report_fields

        fields = _diagnosis_to_report_fields({})
        assert fields["summary"] == "-"
        assert fields["conclusion"] == "-"
        assert fields["suggestion"] == "-"
