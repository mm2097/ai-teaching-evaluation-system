"""会话记忆：进程内保存最近 N 轮对话。

设计：
- 单次会话内保留最近 ``max_rounds`` 轮（默认 5）
- 跨会话不保留（避免上下文污染）
- 会话级上下文：course_id / student_id 由前端注入
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from datetime import datetime
from time import time

from sqlmodel import Session, select

from app.models import AgentConversation


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

    def recent_messages(self, max_rounds: int = 5) -> list[dict]:
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
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def _conversation_from_row(row: AgentConversation) -> Conversation:
    try:
        raw_history = json.loads(row.history_json or "[]")
    except (TypeError, ValueError):
        raw_history = []
    history = [
        ConversationTurn(
            role=item.get("role", "assistant"),
            content=item.get("content", ""),
            tool_calls=item.get("tool_calls", []),
            tool_results=item.get("tool_results", []),
            ts=float(item.get("ts", time())),
        )
        for item in raw_history
        if isinstance(item, dict)
    ]
    return Conversation(
        session_id=row.session_id,
        user_id=row.user_id,
        course_id=row.course_id,
        student_id=row.student_id,
        history=history,
    )


def persist_session(conversation: Conversation, db_session: Session) -> None:
    """Upsert a conversation so it survives a backend restart."""
    row = db_session.exec(
        select(AgentConversation).where(
            AgentConversation.user_id == conversation.user_id,
            AgentConversation.session_id == conversation.session_id,
        )
    ).first()
    history = [
        {
            "role": turn.role,
            "content": turn.content,
            "tool_calls": turn.tool_calls,
            "tool_results": turn.tool_results,
            "ts": turn.ts,
        }
        for turn in conversation.history[-10:]
    ]
    if row is None:
        row = AgentConversation(
            user_id=conversation.user_id,
            session_id=conversation.session_id,
        )
    row.course_id = conversation.course_id
    row.student_id = conversation.student_id
    row.history_json = json.dumps(history, ensure_ascii=False, default=str)
    row.updated_at = datetime.now()
    db_session.add(row)
    db_session.commit()


def delete_persisted_session(session_id: str, user_id: int, db_session: Session) -> None:
    row = db_session.exec(
        select(AgentConversation).where(
            AgentConversation.user_id == user_id,
            AgentConversation.session_id == session_id,
        )
    ).first()
    if row is not None:
        db_session.delete(row)
        db_session.commit()


# ===== 进程内会话表 =====
# 用户 ID 参与索引，避免不同用户传入相同 session_id 时共享上下文。
_sessions: dict[tuple[int, str], Conversation] = {}


def get_or_create_session(
    session_id: str, user_id: int,
    course_id: int | None = None, student_id: int | None = None,
    db_session: Session | None = None,
) -> Conversation:
    """获取或创建会话。"""
    key = (user_id, session_id)
    if key not in _sessions:
        row = None
        if db_session is not None:
            row = db_session.exec(
                select(AgentConversation).where(
                    AgentConversation.user_id == user_id,
                    AgentConversation.session_id == session_id,
                )
            ).first()
        _sessions[key] = _conversation_from_row(row) if row else Conversation(
            session_id=session_id, user_id=user_id,
            course_id=course_id, student_id=student_id,
        )
    else:
        # 更新上下文（前端每次注入最新值）
        s = _sessions[key]
        if course_id is not None:
            s.course_id = course_id
        if student_id is not None:
            s.student_id = student_id
    return _sessions[key]


def clear_session(session_id: str, user_id: int | None = None) -> None:
    if user_id is not None:
        _sessions.pop((user_id, session_id), None)
        return
    for key in [key for key in _sessions if key[1] == session_id]:
        _sessions.pop(key, None)
