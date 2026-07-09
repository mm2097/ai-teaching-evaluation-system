"""会话记忆：进程内保存最近 N 轮对话。

设计：
- 单次会话内保留最近 ``max_rounds`` 轮（默认 6）
- 跨会话不保留（避免上下文污染）
- 会话级上下文：course_id / student_id 由前端注入
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class ConversationTurn:
    """单轮对话记录（含工具调用过程）。"""

    role: str           # user / assistant
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    ts: float = field(default_factory=time)


@dataclass
class Conversation:
    """一次对话会话。"""

    session_id: str
    user_id: int
    course_id: int | None = None
    student_id: int | None = None
    history: list[ConversationTurn] = field(default_factory=list)

    def add_user(self, content: str) -> None:
        self.history.append(ConversationTurn(role="user", content=content))

    def add_assistant(
        self,
        content: str = "",
        tool_calls: list[dict] | None = None,
        tool_results: list[dict] | None = None,
    ) -> None:
        self.history.append(ConversationTurn(
            role="assistant",
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
        ))

    def recent_messages(self, max_rounds: int = 6) -> list[dict]:
        """取最近 N 轮（每轮 user+assistant），转 OpenAI messages 格式。

        含工具调用的历史转为：
            assistant(role=assistant, content, tool_calls)
            tool(role=tool, tool_call_id, content)
        """
        # 截断到最近 max_rounds*2 条（user+assistant 各算一条）
        trimmed = self.history[-(max_rounds * 2):] if self.history else []
        msgs: list[dict] = []
        for turn in trimmed:
            if turn.role == "user":
                msgs.append({"role": "user", "content": turn.content})
            else:
                # assistant
                a: dict = {"role": "assistant", "content": turn.content or ""}
                if turn.tool_calls:
                    # 转 OpenAI 工具调用格式
                    a["tool_calls"] = [
                        {
                            "id": tc.get("id", f"call_{i}"),
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": _safe_json(tc.get("arguments", {})),
                            },
                        }
                        for i, tc in enumerate(turn.tool_calls)
                    ]
                msgs.append(a)
                # 工具结果
                for tr in turn.tool_results:
                    msgs.append({
                        "role": "tool",
                        "tool_call_id": tr.get("tool_call_id", "call_0"),
                        "content": tr.get("content", ""),
                    })
        return msgs


def _safe_json(obj) -> str:
    import json
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


# ===== 进程内会话表 =====
_sessions: dict[str, Conversation] = {}


def get_or_create_session(
    session_id: str, user_id: int,
    course_id: int | None = None, student_id: int | None = None,
) -> Conversation:
    """获取或创建会话。"""
    if session_id not in _sessions:
        _sessions[session_id] = Conversation(
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
            student_id=student_id,
        )
    else:
        # 更新上下文（前端每次注入最新值）
        s = _sessions[session_id]
        s.user_id = user_id
        if course_id is not None:
            s.course_id = course_id
        if student_id is not None:
            s.student_id = student_id
    return _sessions[session_id]


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
