"""大小模型协同:诊断验证层接入测试。

覆盖:
    1. run_agent_stream 诊断完成后产出 verify 事件(mock verify_diagnosis 返回报告)
    2. verify_diagnosis 失败/不可达时不阻断诊断流(返回 None → 无 verify 事件,done 正常)
    3. 非 diagnosis 场景不触发 verify
    4. verify_diagnosis helper 在 algorithm 不可达时返回 None
"""
from __future__ import annotations

import json

import pytest
from sqlmodel import Session

from app.services.agent.llm_proxy import (
    FCResult,
    MockLLMProxy,
    set_llm_proxy,
    verify_diagnosis,
)
from app.services.agent.tools import register_all_tools


@pytest.fixture(autouse=True)
def _setup_tools():
    register_all_tools()


_DIAG_JSON = json.dumps(
    {
        "scope": "class",
        "overall": {"grade": "C", "score": 71, "summary": "班级TCP协议掌握不足"},
        "findings": {"strengths": [], "risks": []},
        "causes": [],
        "suggestions": [],
        "radar": {"成绩": 71, "考勤": 75, "互动": 85, "进步": 60, "综合": 71},
        "meta": {"source": "llm", "toolsUsed": ["get_course_overview"]},
    },
    ensure_ascii=False,
)


def _collect_events(gen) -> list[dict]:
    """收集 run_agent_stream 的所有事件。"""
    return list(gen)


class TestDiagnosisVerifyEvent:
    """诊断流式事件的 verify 接入。"""

    def test_verify_event_emitted_when_report_returned(self, session, engine, monkeypatch):
        """verify_diagnosis 返回报告 → 流里收到 verify 事件。"""
        fake_report = {
            "aligned_kps": ["TCP协议可靠传输"],
            "hallucinated_kps": [],
            "coverage": 0.6,
            "confidence": 0.8,
            "flag": "pass",
            "notes": "ok",
            "matched_chapters": ["ch3"],
        }
        # mock verify_diagnosis 返回假报告
        import app.services.agent.base as base_mod
        monkeypatch.setattr(base_mod, "verify_diagnosis", lambda *a, **kw: fake_report)

        mock = MockLLMProxy([FCResult(content=_DIAG_JSON, tool_calls=[], finish_reason="stop")])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        from app.services.agent.base import run_agent_stream
        events = _collect_events(run_agent_stream(
            session_factory=sf, user_message="诊断班级学情",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        ))

        types = [e["type"] for e in events]
        assert "content" in types          # 诊断内容
        assert "verify" in types           # 验证事件
        assert "done" in types             # 正常结束
        verify_evt = next(e for e in events if e["type"] == "verify")
        assert verify_evt["report"]["flag"] == "pass"
        assert verify_evt["report"]["aligned_kps"] == ["TCP协议可靠传输"]

    def test_verify_failure_does_not_block_diagnosis(self, session, engine, monkeypatch):
        """verify_diagnosis 返回 None → 无 verify 事件,但 content 和 done 正常。"""
        import app.services.agent.base as base_mod
        monkeypatch.setattr(base_mod, "verify_diagnosis", lambda *a, **kw: None)

        mock = MockLLMProxy([FCResult(content=_DIAG_JSON, tool_calls=[], finish_reason="stop")])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        from app.services.agent.base import run_agent_stream
        events = _collect_events(run_agent_stream(
            session_factory=sf, user_message="诊断班级学情",
            user_id=1, course_id=1, agent_type="diagnosis", max_steps=3,
        ))

        types = [e["type"] for e in events]
        assert "content" in types
        assert "done" in types
        assert "verify" not in types  # 验证失败不产出 verify 事件

    def test_non_diagnosis_agent_no_verify(self, session, engine, monkeypatch):
        """qa 场景不触发 verify(verify_diagnosis 不该被调)。"""
        called = {"n": 0}

        def _should_not_call(*a, **kw):
            called["n"] += 1
            return {"flag": "pass"}

        import app.services.agent.base as base_mod
        monkeypatch.setattr(base_mod, "verify_diagnosis", _should_not_call)

        mock = MockLLMProxy([FCResult(content="问答回答", tool_calls=[], finish_reason="stop")])
        set_llm_proxy(mock)

        def sf():
            return Session(engine)

        from app.services.agent.base import run_agent_stream
        events = _collect_events(run_agent_stream(
            session_factory=sf, user_message="张三成绩怎么样",
            user_id=1, course_id=1, agent_type="qa", max_steps=3,
        ))

        types = [e["type"] for e in events]
        assert "content" in types
        assert "verify" not in types
        assert called["n"] == 0  # qa 场景根本没调 verify


class TestVerifyDiagnosisHelper:
    """verify_diagnosis helper 的健壮性。"""

    def test_returns_none_when_algorithm_unreachable(self):
        """algorithm 服务不可达时返回 None,不抛异常。"""
        # 8001 没起服务(测试环境),应返回 None
        report = verify_diagnosis("TCP协议", course_id=1, base_url="http://127.0.0.1:59999", timeout=1.0)
        assert report is None

    def test_returns_none_on_empty_content(self):
        """空内容也安全调用(不抛异常)。"""
        # 即使算法服务不可达,空内容也不该崩
        report = verify_diagnosis("", course_id=1, base_url="http://127.0.0.1:59999", timeout=1.0)
        assert report is None
