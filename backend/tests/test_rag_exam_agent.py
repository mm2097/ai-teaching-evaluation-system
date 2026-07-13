"""LLM Tool Loop RAG 出题 Agent 单元测试。

覆盖（对应 LLM_Tool_Loop_RAG出题Agent设计.md）：
    L1 工具单测：
        - search_question_bank     题库结构化检索
        - rag_search_questions     RAG 语义召回
        - get_recent_used_questions 历史出题查询
        - validate_paper           组卷校验
    L2 FC 循环（Mock LLM）：
        - 完整出题流程（检索 → RAG → 排重 → 校验 → 组卷）
        - 信息不足澄清流程
        - 题库不足时 AI 补题流程
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


# ============================================================
# L1 工具单测
# ============================================================

class TestSearchQuestionBank:
    """工具 1：题库结构化检索。"""

    def test_search_all(self, session):
        """无过滤条件 → 返回全部题。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(_ctx(session), course_id=1)
        assert result["total"] >= 12  # 种子数据有 12 题
        assert len(result["questions"]) == result["total"]

    def test_filter_by_knowledge_point(self, session):
        """按知识点过滤。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(_ctx(session), course_id=1, knowledge_points=["二叉树"])
        assert result["total"] >= 3
        for q in result["questions"]:
            assert q["knowledge_point"] == "二叉树"

    def test_filter_by_type(self, session):
        """按题型过滤（1=单选）。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(_ctx(session), course_id=1, question_types=[1])
        for q in result["questions"]:
            assert q["type"] == "single_choice"

    def test_filter_by_difficulty(self, session):
        """按难度过滤。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(_ctx(session), course_id=1, difficulty="hard")
        for q in result["questions"]:
            assert q["difficulty"] == "hard"

    def test_combined_filter(self, session):
        """组合过滤：知识点 + 题型 + 难度。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(
            _ctx(session), course_id=1,
            knowledge_points=["红黑树"],
            question_types=[1],
            difficulty="hard",
        )
        assert result["total"] >= 1
        for q in result["questions"]:
            assert q["knowledge_point"] == "红黑树"
            assert q["type"] == "single_choice"
            assert q["difficulty"] == "hard"

    def test_no_match(self, session):
        """无匹配返回空列表。"""
        from app.services.agent.tools.exam import _t_search_question_bank
        result = _t_search_question_bank(
            _ctx(session), course_id=1, knowledge_points=["不存在的知识点"]
        )
        assert result["total"] == 0


class TestRagSearchQuestions:
    """工具 2：RAG 语义召回。"""

    def test_semantic_recall(self, session):
        """查询"二叉树遍历"应召回二叉树相关题。"""
        from app.services.agent.tools.exam import _t_rag_search_questions
        result = _t_rag_search_questions(_ctx(session), course_id=1, query="二叉树遍历")
        assert result["total"] > 0
        # Top 结果应该包含"二叉树"相关题干
        top = result["questions"][0]
        assert "similarity" in top
        assert "二叉树" in top["content"] or "先序" in top["content"]

    def test_sorting_by_similarity(self, session):
        """结果应按相似度降序排列。"""
        from app.services.agent.tools.exam import _t_rag_search_questions
        result = _t_rag_search_questions(_ctx(session), course_id=1, query="排序算法时间复杂度")
        sims = [q["similarity"] for q in result["questions"]]
        assert sims == sorted(sims, reverse=True)

    def test_top_k_limit(self, session):
        """top_k 参数生效。"""
        from app.services.agent.tools.exam import _t_rag_search_questions
        result = _t_rag_search_questions(_ctx(session), course_id=1, query="数据结构", top_k=3)
        assert len(result["questions"]) <= 3

    def test_empty_query_error(self, session):
        """空 query 返回错误。"""
        from app.services.agent.tools.exam import _t_rag_search_questions
        result = _t_rag_search_questions(_ctx(session), course_id=1, query="")
        assert "error" in result


class TestGetRecentUsedQuestions:
    """工具 3：历史出题查询。"""

    def test_recent_tasks(self, session):
        """返回近期任务及用过的题。"""
        from app.services.agent.tools.exam import _t_get_recent_used_questions
        result = _t_get_recent_used_questions(_ctx(session), course_id=1)
        assert len(result["tasks"]) >= 2  # 种子数据有 2 个任务
        assert len(result["used_questions"]) >= 3  # 至少 3 道题被用
        assert len(result["used_question_ids"]) >= 3

    def test_used_in_tasks_tracking(self, session):
        """每道被用过的题记录来源任务。"""
        from app.services.agent.tools.exam import _t_get_recent_used_questions
        result = _t_get_recent_used_questions(_ctx(session), course_id=1)
        for q in result["used_questions"]:
            assert "used_in_tasks" in q
            assert len(q["used_in_tasks"]) >= 1

    def test_recent_count_limit(self, session):
        """recent_count 限制任务数。"""
        from app.services.agent.tools.exam import _t_get_recent_used_questions
        result = _t_get_recent_used_questions(_ctx(session), course_id=1, recent_count=1)
        assert len(result["tasks"]) <= 1

    def test_no_tasks(self, session):
        """无任务的课程返回空。"""
        from app.services.agent.tools.exam import _t_get_recent_used_questions
        result = _t_get_recent_used_questions(_ctx(session), course_id=999)
        assert result["used_questions"] == []
        assert result["used_question_ids"] == []


class TestValidatePaper:
    """工具 4：组卷校验。"""

    def test_valid_paper_passes(self, session):
        """完整无重复的方案应通过校验。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "二叉树第k层最多多少节点？", "type": "single_choice",
             "options": ["A.2^k", "B.2^(k-1)", "C.k", "D.2k"], "correct_answer": "B",
             "knowledge_point": "二叉树"},
            {"content": "快速排序是稳定排序吗？", "type": "judge",
             "correct_answer": "false", "knowledge_point": "快速排序"},
        ]
        result = _t_validate_paper(_ctx(session), questions=questions, target_count=2)
        assert result["passed"] is True
        assert result["issue_count"] == 0

    def test_missing_answer_detected(self, session):
        """缺少答案应报 issue。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "测试题", "type": "single_choice", "options": ["A.x", "B.y"], "correct_answer": ""},
        ]
        result = _t_validate_paper(_ctx(session), questions=questions)
        assert result["passed"] is False
        assert any("缺少答案" in i for i in result["issues"])

    def test_insufficient_options_detected(self, session):
        """选择题选项不足应报 issue。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "测试题", "type": "single_choice", "options": ["仅一项"], "correct_answer": "A"},
        ]
        result = _t_validate_paper(_ctx(session), questions=questions)
        assert result["passed"] is False
        assert any("选项不足" in i for i in result["issues"])

    def test_internal_duplicate_detected(self, session):
        """内部重复应报 issue。"""
        from app.services.agent.tools.exam import _t_validate_paper
        q = {"content": "完全相同的二叉树题目", "type": "single_choice",
             "options": ["A.1", "B.2"], "correct_answer": "A", "knowledge_point": "二叉树"}
        result = _t_validate_paper(_ctx(session), questions=[q, dict(q)])
        assert result["passed"] is False
        assert any("重复" in i for i in result["issues"])

    def test_target_count_warning(self, session):
        """题量不足目标应告警。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "题1", "type": "judge", "correct_answer": "true", "knowledge_point": "二叉树"},
        ]
        result = _t_validate_paper(_ctx(session), questions=questions, target_count=10)
        assert result["warning_count"] >= 1
        assert any("题量不足" in w for w in result["warnings"])

    def test_knowledge_coverage_warning(self, session):
        """未覆盖目标知识点应告警。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "题1", "type": "judge", "correct_answer": "true", "knowledge_point": "二叉树"},
        ]
        result = _t_validate_paper(
            _ctx(session), questions=questions,
            target_knowledge_points=["二叉树", "红黑树", "快速排序"],
        )
        assert any("未覆盖" in w for w in result["warnings"])

    def test_type_distribution_warning(self, session):
        """题型比例不达标应告警。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "题1", "type": "judge", "correct_answer": "true"},
        ]
        result = _t_validate_paper(
            _ctx(session), questions=questions,
            target_types={"single_choice": 5},
        )
        assert any("single_choice" in w for w in result["warnings"])

    def test_summary_output(self, session):
        """校验返回 summary 统计。"""
        from app.services.agent.tools.exam import _t_validate_paper
        questions = [
            {"content": "题1", "type": "single_choice", "options": ["A.x","B.y"],
             "correct_answer": "A", "knowledge_point": "二叉树"},
            {"content": "题2", "type": "judge", "correct_answer": "true", "knowledge_point": "排序"},
        ]
        result = _t_validate_paper(_ctx(session), questions=questions)
        assert result["summary"]["total_questions"] == 2
        assert "single_choice" in result["summary"]["actual_types"]
        assert "二叉树" in result["summary"]["actual_knowledge_points"]


# ============================================================
# L2 FC 循环测试（Mock LLM）
# ============================================================

class TestRAGExamAgentFCLoop:
    """模拟 LLM 驱动完整的 RAG 出题 Agent 流程。"""

    def test_full_exam_flow(self, session, engine):
        """完整流程：检索 → RAG → 排重 → 校验 → 组卷。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        mock = MockLLMProxy([
            # Step 1: 调 search_question_bank 检索二叉树选择题
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "search_question_bank", "arguments": {
                    "course_id": 1, "knowledge_points": ["二叉树"], "question_types": [1]
                }},
            ], finish_reason="tool_calls"),
            # Step 2: 调 rag_search_questions 语义补充
            FCResult(content="", tool_calls=[
                {"id": "c2", "name": "rag_search_questions", "arguments": {
                    "course_id": 1, "query": "二叉树遍历节点"
                }},
            ], finish_reason="tool_calls"),
            # Step 3: 调 get_recent_used_questions 排重
            FCResult(content="", tool_calls=[
                {"id": "c3", "name": "get_recent_used_questions", "arguments": {
                    "course_id": 1
                }},
            ], finish_reason="tool_calls"),
            # Step 4: 调 validate_paper 校验
            FCResult(content="", tool_calls=[
                {"id": "c4", "name": "validate_paper", "arguments": {
                    "course_id": 1,
                    "questions": [
                        {"content": "二叉树第k层节点数", "type": "single_choice",
                         "options": ["A.1","B.2","C.3","D.4"], "correct_answer": "A",
                         "knowledge_point": "二叉树"},
                    ],
                    "target_count": 1,
                }},
            ], finish_reason="tool_calls"),
            # Step 5: 调 compose_paper_plan 组卷
            FCResult(content="", tool_calls=[
                {"id": "c5", "name": "compose_paper_plan", "arguments": {
                    "course_id": 1,
                    "questions": [
                        {"content": "二叉树第k层节点数", "type": "single_choice",
                         "options": ["A.1","B.2","C.3","D.4"], "correct_answer": "A",
                         "knowledge_point": "二叉树"},
                    ],
                    "plan_note": "二叉树小测",
                }},
            ], finish_reason="tool_calls"),
            # Step 6: 最终输出
            FCResult(
                content="【组卷方案】\n二叉树小测，1 题单选。\n请审核。\n【数据来源】search_question_bank / rag_search_questions / validate_paper / compose_paper_plan",
                tool_calls=[], finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="出一套二叉树小测，1 道选择题",
            user_id=1, course_id=1, agent_type="exam", max_steps=6,
        )

        assert "组卷方案" in result.answer
        assert len(result.steps) >= 5
        assert result.error is None
        # 验证各工具均被调用
        tool_names = [tc.name for s in result.steps for tc in s.tool_calls]
        assert "search_question_bank" in tool_names
        assert "rag_search_questions" in tool_names
        assert "validate_paper" in tool_names
        assert "compose_paper_plan" in tool_names

    def test_clarification_flow(self, session, engine):
        """信息不足时 LLM 应直接澄清而非调工具。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        mock = MockLLMProxy([
            # LLM 判断信息不足，直接输出澄清（无 tool_calls）
            FCResult(
                content="需要多少道题？难度偏易还是偏难？",
                tool_calls=[], finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="帮我出点二叉树的题",
            user_id=1, course_id=1, agent_type="exam", max_steps=3,
        )

        assert "多少道" in result.answer or "难度" in result.answer
        assert len(result.steps) == 1
        assert len(result.steps[0].tool_calls) == 0  # 未调用任何工具

    def test_weak_points_driven_flow(self, session, engine):
        """薄弱点驱动流程：先查薄弱点 → 按薄弱点检索 → 组卷。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        mock = MockLLMProxy([
            # Step 1: 调 get_weak_knowledge_points
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "get_weak_knowledge_points", "arguments": {
                    "course_id": 1, "top_k": 3
                }},
            ], finish_reason="tool_calls"),
            # Step 2: 最终输出
            FCResult(
                content="班级薄弱点已分析，建议针对红黑树出题。【数据来源】get_weak_knowledge_points",
                tool_calls=[], finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="针对薄弱点出题",
            user_id=1, course_id=1, agent_type="exam", max_steps=3,
        )

        assert "薄弱点" in result.answer
        assert result.steps[0].tool_calls[0].name == "get_weak_knowledge_points"
        # 验证工具返回了真实数据
        weak_result = result.steps[0].tool_calls[0].result
        assert "weak_points" in weak_result
        assert len(weak_result["weak_points"]) > 0

    def test_tool_error_handling(self, session, engine):
        """工具参数错误时优雅降级。"""
        from app.services.agent.base import run_agent
        from app.services.agent.llm_proxy import set_llm_proxy

        mock = MockLLMProxy([
            FCResult(content="", tool_calls=[
                {"id": "c1", "name": "rag_search_questions", "arguments": {
                    "course_id": 1, "query": ""
                }},
            ], finish_reason="tool_calls"),
            FCResult(
                content="查询条件有误，请提供搜索关键词。",
                tool_calls=[], finish_reason="stop",
            ),
        ])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        result = run_agent(
            session_factory=sf,
            user_message="帮我搜题",
            user_id=1, course_id=1, agent_type="exam", max_steps=3,
        )

        # 工具返回 error 但 Agent 不应崩溃
        assert result.error is None
        tool_result = result.steps[0].tool_calls[0].result
        assert "error" in tool_result
