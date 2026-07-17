"""Agent 工具 + FC 循环单元测试。

覆盖：
    L1 工具单测：10 个查询工具 + 4 个组卷工具
    L2 FC 循环：用 MockLLMProxy 模拟工具调用
    L4 安全：写操作拒绝、不存在工具拒绝
"""
from __future__ import annotations

import pytest
from sqlmodel import Session

from app.services.agent.registry import ToolContext, get_registry
from app.services.agent.tools import register_all_tools
from app.services.agent.llm_proxy import MockLLMProxy, FCResult


@pytest.fixture(autouse=True)
def _setup_tools():
    """每个测试前确保工具已注册。"""
    register_all_tools()


def _ctx(session: Session, **kw) -> ToolContext:
    return ToolContext(session=session, user_id=1, course_id=1, **kw)


# ===== L1 查询工具单测 =====

class TestQueryTools:
    def test_get_course_overview(self, session):
        from app.services.agent.tools.queries import _t_get_course_overview
        result = _t_get_course_overview(_ctx(session), course_id=1)
        assert result["course_id"] == 1
        assert result["student_count"] == 3
        assert result["course_name"] == "数据结构"
        # 最近一次（期中）均分 = (55+68+80)/3 ≈ 67.7
        assert 60 <= result["avg_score"] <= 75

    def test_get_score_list(self, session):
        from app.services.agent.tools.queries import _t_get_score_list
        result = _t_get_score_list(_ctx(session), course_id=1)
        assert "scores" in result
        assert len(result["scores"]) == 3
        # 第一名应该是王五（80分）
        assert result["scores"][0]["name"] == "王五"
        assert result["scores"][0]["score"] == 80.0

    def test_get_score_trend_class(self, session):
        from app.services.agent.tools.queries import _t_get_score_trend
        result = _t_get_score_trend(_ctx(session), course_id=1)
        assert result["scope"] == "class"
        assert len(result["trend"]) == 3  # 3 次考核

    def test_get_score_trend_student(self, session):
        from app.services.agent.tools.queries import _t_get_score_trend
        result = _t_get_score_trend(_ctx(session), course_id=1, student_id=1)
        assert result["scope"] == "student"
        assert len(result["trend"]) == 3
        # 张三 85→75→55
        assert result["trend"][0]["score"] == 85.0
        assert result["trend"][2]["score"] == 55.0

    def test_get_attendance(self, session):
        from app.services.agent.tools.queries import _t_get_attendance
        result = _t_get_attendance(_ctx(session), course_id=1, student_id=1)
        assert result["student_id"] == 1
        # 张三：1 次出勤 + 3 次缺勤 = 25%
        assert result["rate"] == 25.0
        assert len(result["absent_dates"]) == 3

    def test_get_knowledge_mastery(self, session):
        from app.services.agent.tools.queries import _t_get_knowledge_mastery
        result = _t_get_knowledge_mastery(_ctx(session), course_id=1, student_id=1)
        assert result["scope"] == "student"
        assert len(result["points"]) > 0

    def test_get_weak_knowledge_points(self, session):
        from app.services.agent.tools.queries import _t_get_weak_knowledge_points
        result = _t_get_weak_knowledge_points(_ctx(session), course_id=1, top_k=3)
        assert "weak_points" in result
        assert len(result["weak_points"]) <= 3

    def test_get_warning_students(self, session):
        from app.services.agent.tools.queries import _t_get_warning_students
        result = _t_get_warning_students(_ctx(session), course_id=1)
        assert "warning_students" in result

    def test_get_student_detail(self, session):
        from app.services.agent.tools.queries import _t_get_student_detail
        result = _t_get_student_detail(_ctx(session), course_id=1, student_id=1)
        assert result["name"] == "张三"
        assert len(result["scores"]) == 3
        assert result["attendance_rate"] == 25.0

    def test_search_student(self, session):
        from app.services.agent.tools.queries import _t_search_student
        # 按姓名搜
        result = _t_search_student(_ctx(session), keyword="张")
        assert len(result["students"]) == 1
        assert result["students"][0]["name"] == "张三"
        # 按学号搜
        result = _t_search_student(_ctx(session), keyword="2024")
        assert len(result["students"]) == 3

    def test_get_exercise_records(self, session):
        from app.services.agent.tools.queries import _t_get_exercise_records
        result = _t_get_exercise_records(_ctx(session), course_id=1)
        assert "records" in result


# ===== L1 组卷工具单测 =====

class TestExamTools:
    def test_get_existing_exercises(self, session):
        from app.services.agent.tools.exam import _t_get_existing_exercises
        result = _t_get_existing_exercises(_ctx(session), course_id=1)
        assert "existing_count" in result
        assert result["existing_count"] >= 1

    def test_compose_paper_plan(self, session):
        from app.services.agent.tools.exam import _t_compose_paper_plan
        questions = [
            {"stem": "题1", "type": "single_choice", "knowledge_point": "红黑树"},
            {"stem": "题2", "type": "judge", "knowledge_point": "快速排序"},
        ]
        result = _t_compose_paper_plan(_ctx(session), course_id=1, questions=questions, plan_note="测试")
        assert result["status"] == "draft"
        assert result["total"] == 2
        assert "红黑树" in result["distribution_by_knowledge_point"]

    def test_check_duplicate(self, session):
        from app.services.agent.tools.exam import _t_check_duplicate_wrapper
        # 与 seed 中题目完全相同（含选项）→ 应判重
        new_qs = [{
            "content": "红黑树的性质不包括以下哪项？",
            "options": ["A.每个节点是红色或黑色", "B.根节点是黑色", "C.叶子节点是红色", "D.红色节点的子节点是黑色"],
            "correct_answer": "C",
        }]
        result = _t_check_duplicate_wrapper(_ctx(session), course_id=1, new_questions=new_qs)
        assert "total_checked" in result
        assert result["total_checked"] == 1
        # 相同题干 + 相同选项 → 高相似度
        assert result["details"][0]["similarity"] > 0.5


# ===== L2 FC 循环测试（Mock LLM） =====

class TestFCLoop:
    def test_tool_execution_flow(self, session, engine):
        """模拟 LLM 调用 get_course_overview 工具。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        # Mock：第 1 步调工具，第 2 步给最终答案
        mock = MockLLMProxy([
            FCResult(
                content="",
                tool_calls=[{"id": "call_1", "name": "get_course_overview", "arguments": {"course_id": 1}}],
                finish_reason="tool_calls",
            ),
            FCResult(
                content="课程数据结构有 3 名学生，最近均分约 67.7。【数据来源】get_course_overview",
                tool_calls=[],
                finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="班里情况怎么样",
            user_id=1,
            course_id=1,
            agent_type="qa",
            max_steps=3,
        )

        assert "数据结构" in result.answer or "3" in result.answer
        assert len(result.steps) >= 2
        assert result.steps[0].tool_calls[0].name == "get_course_overview"
        assert result.steps[0].tool_calls[0].result is not None
        assert result.steps[0].tool_calls[0].result["student_count"] == 3
        assert result.error is None

    def test_multi_tool_chain(self, session, engine):
        """模拟多步工具调用链。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_score_trend", "arguments": {"course_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content="", tool_calls=[
                {"id": "c2", "name": "get_student_detail", "arguments": {"course_id": 1, "student_id": 1}},
            ], finish_reason="tool_calls"),
            FCResult(content="张三期中 55 分，持续下滑。【数据来源】get_score_trend / get_student_detail",
                     tool_calls=[], finish_reason="stop"),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="谁退步最大",
            user_id=1, course_id=1, agent_type="qa", max_steps=5,
        )

        assert "张三" in result.answer
        assert len(result.steps) == 3
        assert result.total_tokens == 0  # mock 不计 token
        # 验证工具确实被执行
        assert result.steps[0].tool_calls[0].result is not None
        assert result.steps[1].tool_calls[0].result is not None

    def test_llm_error_graceful(self, session, engine):
        """LLM 服务不可用时优雅降级。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy, LLMProxy, FCResult
        from abc import abstractmethod

        class FailingProxy(LLMProxy):
            def chat_with_tools(self, messages, tools, tool_choice="auto"):
                raise RuntimeError("LLM 服务不可用")

        set_llm_proxy(FailingProxy())

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="你好",
            user_id=1, course_id=1, agent_type="qa", max_steps=2,
        )
        assert result.error is not None
        assert "不可用" in result.answer or "困难" in result.answer


# ===== L3 学生助学 Agent（Tutor）测试 =====

class TestTutorAgent:
    def test_tutor_setup_has_no_tools(self):
        """tutor 不挂载任何工具，从机制上杜绝越权查班级数据。"""
        from app.services.agent.base import _resolve_agent_setup
        from app.services.agent.prompts import TUTOR_SYSTEM_PROMPT

        registry = get_registry()
        prompt, schemas = _resolve_agent_setup("tutor", registry, allow_mutation=False)
        assert prompt == TUTOR_SYSTEM_PROMPT
        assert schemas == []

    def test_qa_and_exam_still_have_tools(self):
        """qa / exam 仍然挂载全部查询工具。"""
        from app.services.agent.base import _resolve_agent_setup
        registry = get_registry()
        _, qa_schemas = _resolve_agent_setup("qa", registry, allow_mutation=False)
        _, exam_schemas = _resolve_agent_setup("exam", registry, allow_mutation=False)
        assert len(qa_schemas) >= 10
        assert len(exam_schemas) >= 10

    def test_tutor_never_calls_tools_in_loop(self, session, engine):
        """即使 LLM 想调工具，tutor 没有工具可用，只走纯文本回答。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        # tutor 场景 LLM 直接给启发式回答（不含最终答案）
        mock = MockLLMProxy([
            FCResult(
                content="先想想：红黑树插入后如果父节点是红色，你需要看叔叔节点的颜色。你觉得下一步该判断什么？",
                tool_calls=[],
                finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="红黑树插入这道题答案是什么",
            user_id=1,
            course_id=1,
            agent_type="tutor",
            max_steps=3,
        )
        # 无工具调用步骤
        assert all(len(s.tool_calls) == 0 for s in result.steps)
        assert result.error is None
        assert result.answer  # 有回答


# ===== L4 安全测试 =====

class TestSafety:
    def test_unknown_tool(self, session):
        """调用不存在的工具应返回错误而非崩溃。"""
        registry = get_registry()
        ctx = _ctx(session)
        result = registry.execute("nonexistent_tool", ctx, {})
        assert "error" in result
        assert "不存在" in result["error"]

    def test_mutation_blocked_by_default(self, session):
        """写操作在未授权时应被拒绝。"""
        from app.services.agent.registry import Tool, ToolContext
        registry = get_registry()

        # 注册一个 mutation 工具
        def dangerous_handler(ctx, **kw):
            return {"deleted": "everything"}
        registry.register(Tool(
            name="_test_dangerous",
            description="测试用危险工具",
            parameters={"type": "object", "properties": {}},
            handler=dangerous_handler,
            category="mutation",
        ))

        ctx = ToolContext(session=session, user_id=1, course_id=1, allow_mutation=False)
        result = registry.execute("_test_dangerous", ctx, {})
        assert "error" in result
        assert "未授权" in result["error"]
