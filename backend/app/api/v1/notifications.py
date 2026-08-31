"""消息通知 API：学生接收教师发送的预警通知。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import Course, Notification, Student, SysUser

router = APIRouter()


def _student_of_user(session: Session, current_user: SysUser) -> Student:
    """校验并返回当前用户绑定的学生档案（仅学生角色可查看通知）。"""
    student = session.exec(
        select(Student).where(Student.user_id == current_user.user_id)
    ).first()
    if not student:
        raise HTTPException(status_code=403, detail="当前账号未关联学生档案")
    return student


def _notification_response(n: Notification, course: Course | None) -> dict:
    return {
        "id": n.notification_id,
        "title": n.title,
        "content": n.content,
        "courseId": n.course_id,
        "courseName": course.course_name if course else "",
        "warningId": n.warning_id,
        "isRead": n.is_read == 1,
        "createTime": n.create_time.strftime("%Y-%m-%d %H:%M") if n.create_time else "",
    }


@router.get("/notifications", tags=["消息通知"])
def list_notifications(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """学生查看自己的站内通知（最新 50 条，含未读状态）。"""
    student = _student_of_user(session, current_user)

    rows = session.exec(
        select(Notification)
        .where(Notification.student_id == student.student_id)
        .order_by(Notification.create_time.desc())  # type: ignore[attr-defined]
        .limit(50)
    ).all()

    course_ids = {r.course_id for r in rows if r.course_id}
    courses = {
        c.course_id: c
        for c in session.exec(select(Course).where(Course.course_id.in_(course_ids))).all()  # type: ignore[arg-type]
    }
    return [_notification_response(n, courses.get(n.course_id)) for n in rows]


@router.put("/notifications/{notification_id}/read", tags=["消息通知"])
def mark_notification_read(
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """将单条通知标记为已读（仅通知接收学生本人可操作）。"""
    student = _student_of_user(session, current_user)

    notification = session.get(Notification, notification_id)
    if not notification or notification.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = 1
    session.add(notification)
    session.commit()
    session.refresh(notification)

    course = session.get(Course, notification.course_id) if notification.course_id else None
    return _notification_response(notification, course)


@router.put("/notifications/read-all", tags=["消息通知"])
def mark_all_notifications_read(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """将当前学生的全部通知标记为已读。返回更新条数。"""
    student = _student_of_user(session, current_user)

    unread = session.exec(
        select(Notification).where(
            Notification.student_id == student.student_id,
            Notification.is_read == 0,
        )
    ).all()
    for n in unread:
        n.is_read = 1
        session.add(n)
    session.commit()

    return {"updated": len(unread)}
