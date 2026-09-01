"""预警通知（教师发送 → 学生接收）回归测试。

conftest 种子数据：
- 教师 user_id=1（王老师），课程 1；学生 user_id=2/3/4（张三/李四/王五）
- 预警 warning_id=1：课程 1、学生 1（张三）、未处理
"""
from fastapi import HTTPException
import pytest
from sqlmodel import select

from app.api.v1 import analysis, notifications
from app.models import Notification, StudyWarning, SysUser


def _user(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


def _notify(session, user_id: int, warning_id: int) -> dict:
    return analysis.notify_warning_student(
        warning_id,
        session=session,
        current_user=_user(session, user_id),
    )


def _make_warning(session, student_id: int, warning_type: str = "W1:成绩下滑") -> StudyWarning:
    warning = StudyWarning(
        course_id=1, student_id=student_id,
        warning_type=warning_type, warning_level=2,
        warning_reason="期中较上次下滑20分", handle_status=0,
    )
    session.add(warning)
    session.commit()
    session.refresh(warning)
    return warning


def test_teacher_notify_creates_notification_and_blocks_duplicate(session):
    result = _notify(session, 1, 1)

    assert result["studentName"] == "张三"
    assert result["title"].startswith("学情预警")

    notification = session.exec(
        select(Notification).where(Notification.warning_id == 1)
    ).one()
    assert notification.student_id == 1
    assert notification.course_id == 1
    assert notification.is_read == 0
    assert "下滑" in notification.content

    # 同一预警重复发送 → 409
    with pytest.raises(HTTPException) as exc_info:
        _notify(session, 1, 1)
    assert exc_info.value.status_code == 409


def test_notify_requires_teacher_and_existing_warning(session):
    # 学生无权发送通知
    with pytest.raises(HTTPException) as exc_info:
        _notify(session, 2, 1)
    assert exc_info.value.status_code == 403

    # 预警不存在 → 404
    with pytest.raises(HTTPException) as exc_info:
        _notify(session, 1, 999)
    assert exc_info.value.status_code == 404


def test_get_warnings_exposes_notified_flag(session):
    warning = _make_warning(session, 2, warning_type="W2:成绩暴跌")
    warning_id = warning.warning_id

    teacher = _user(session, 1)
    before = analysis.get_warnings(
        course_id=1, class_id=None, level=None, status=0, student_id=None,
        session=session, current_user=teacher,
    )
    row_before = next(w for w in before if w["id"] == warning_id)
    assert row_before["notified"] is False

    _notify(session, 1, warning_id)

    after = analysis.get_warnings(
        course_id=1, class_id=None, level=None, status=0, student_id=None,
        session=session, current_user=teacher,
    )
    row_after = next(w for w in after if w["id"] == warning_id)
    assert row_after["notified"] is True


def test_student_lists_own_notifications_only(session):
    session.add(Notification(
        course_id=1, student_id=1, warning_id=None,
        title="张三的专属通知", content="测试内容", is_read=0,
    ))
    session.commit()

    zhang = notifications.list_notifications(
        session=session, current_user=_user(session, 2),
    )
    assert any(n["title"] == "张三的专属通知" for n in zhang)

    li = notifications.list_notifications(
        session=session, current_user=_user(session, 3),
    )
    assert all(n["title"] != "张三的专属通知" for n in li)

    # 教师账号未关联学生档案 → 403
    with pytest.raises(HTTPException) as exc_info:
        notifications.list_notifications(
            session=session, current_user=_user(session, 1),
        )
    assert exc_info.value.status_code == 403


def test_student_marks_notification_read_and_read_all(session):
    session.add(Notification(
        course_id=1, student_id=1, warning_id=None,
        title="未读1", content="a", is_read=0,
    ))
    session.add(Notification(
        course_id=1, student_id=1, warning_id=None,
        title="未读2", content="b", is_read=0,
    ))
    session.commit()
    ids = session.exec(
        select(Notification.notification_id).where(
            Notification.student_id == 1, Notification.is_read == 0,
        )
    ).all()

    # 单条已读
    first = notifications.mark_notification_read(
        ids[0], session=session, current_user=_user(session, 2),
    )
    assert first["isRead"] is True

    # 他人（李四）不可读张三的通知
    with pytest.raises(HTTPException) as exc_info:
        notifications.mark_notification_read(
            ids[1], session=session, current_user=_user(session, 3),
        )
    assert exc_info.value.status_code == 404

    # 全部已读
    result = notifications.mark_all_notifications_read(
        session=session, current_user=_user(session, 2),
    )
    assert result["updated"] >= 1
    remaining = session.exec(
        select(Notification).where(
            Notification.student_id == 1, Notification.is_read == 0,
        )
    ).all()
    assert remaining == []
