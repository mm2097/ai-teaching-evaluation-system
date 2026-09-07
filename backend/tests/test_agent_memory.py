from app.services.agent.memory import (
    clear_session,
    get_or_create_session,
    persist_session,
)


def test_sessions_with_same_id_are_isolated_by_user() -> None:
    session_id = "shared-browser-session"
    first = get_or_create_session(session_id, user_id=101, course_id=1)
    second = get_or_create_session(session_id, user_id=202, course_id=1)

    first.add_user("第一位教师的分析内容")

    assert first is not second
    assert second.recent_messages() == []

    clear_session(session_id, user_id=101)
    assert get_or_create_session(session_id, user_id=202, course_id=1) is second

    clear_session(session_id, user_id=202)


def test_session_is_restored_from_database_after_process_memory_is_cleared(session) -> None:
    session_id = "restartable-session"
    conversation = get_or_create_session(session_id, user_id=1, course_id=1, db_session=session)
    conversation.add_user("请分析这门课的薄弱点")
    conversation.add_assistant("薄弱点主要集中在网络协议。")
    persist_session(conversation, session)

    clear_session(session_id, user_id=1)
    restored = get_or_create_session(session_id, user_id=1, db_session=session)

    assert [item["content"] for item in restored.recent_messages()] == [
        "请分析这门课的薄弱点",
        "薄弱点主要集中在网络协议。",
    ]
    clear_session(session_id, user_id=1)
