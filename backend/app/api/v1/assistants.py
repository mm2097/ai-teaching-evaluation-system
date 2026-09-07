"""助教档案、课程授权与工作台接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_client_ip, get_current_user, save_operation_log
from app.core.permissions import require_admin, require_assistant
from app.models import Course, CourseAssistant, SysUser, TeachingAssistant

router = APIRouter()


class AssistantCourseAssignment(BaseModel):
    course_ids: list[int] = Field(default_factory=list, max_length=100)


def _course_dict(course: Course) -> dict:
    return {
        "course_id": course.course_id,
        "course_code": course.course_code,
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "semester": course.semester,
        "college": course.college,
        "credit": course.credit,
        "status": course.status,
    }


def get_assistant_for_user(session: Session, user_id: int) -> TeachingAssistant:
    assistant = session.exec(
        select(TeachingAssistant).where(TeachingAssistant.user_id == user_id)
    ).first()
    if not assistant:
        raise HTTPException(status_code=403, detail="当前助教账号未关联助教档案")
    return assistant


def get_assistant_course_ids(session: Session, assistant_id: int) -> list[int]:
    return list(session.exec(
        select(CourseAssistant.course_id).where(
            CourseAssistant.assistant_id == assistant_id
        )
    ).all())


@router.get("/assistants/me", tags=["助教管理"])
def get_my_assistant_profile(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_assistant),
) -> dict:
    """返回当前助教档案及可协助维护的课程。"""
    assistant = get_assistant_for_user(session, current_user.user_id)
    course_ids = get_assistant_course_ids(session, assistant.assistant_id)
    courses = session.exec(
        select(Course).where(Course.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all() if course_ids else []
    return {
        "assistant_id": assistant.assistant_id,
        "assistant_no": assistant.assistant_no,
        "real_name": assistant.real_name,
        "college": assistant.college,
        "phone": assistant.phone,
        "email": assistant.email,
        "courses": [_course_dict(course) for course in courses],
    }


@router.get("/assistants", tags=["助教管理"])
def list_assistants(
    session: Session = Depends(get_session),
    _current_user: SysUser = Depends(require_admin),
) -> list[dict]:
    """管理员查看助教档案和课程授权。"""
    assistants = session.exec(select(TeachingAssistant)).all()
    rows = []
    for assistant in assistants:
        course_ids = get_assistant_course_ids(session, assistant.assistant_id)
        rows.append({
            "assistant_id": assistant.assistant_id,
            "assistant_no": assistant.assistant_no,
            "real_name": assistant.real_name,
            "user_id": assistant.user_id,
            "college": assistant.college,
            "phone": assistant.phone,
            "email": assistant.email,
            "course_ids": course_ids,
        })
    return rows


@router.put("/assistants/{assistant_id}/courses", tags=["助教管理"])
def assign_assistant_courses(
    assistant_id: int,
    payload: AssistantCourseAssignment,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """管理员覆盖设置助教可维护的课程，空列表表示取消全部授权。"""
    assistant = session.get(TeachingAssistant, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="助教档案不存在")

    course_ids = list(dict.fromkeys(payload.course_ids))
    existing_courses = session.exec(
        select(Course).where(Course.course_id.in_(course_ids))  # type: ignore[arg-type]
    ).all() if course_ids else []
    if len(existing_courses) != len(course_ids):
        found = {course.course_id for course in existing_courses}
        missing = sorted(set(course_ids) - found)
        raise HTTPException(status_code=400, detail=f"课程不存在：{missing}")

    old_rows = session.exec(
        select(CourseAssistant).where(CourseAssistant.assistant_id == assistant_id)
    ).all()
    for row in old_rows:
        session.delete(row)
    for course_id in course_ids:
        session.add(CourseAssistant(
            assistant_id=assistant_id,
            course_id=course_id,
            create_time=datetime.now(),
        ))
    session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="助教管理",
        operation="课程授权",
        content=f"为助教 {assistant.real_name} 设置课程：{course_ids}",
        ip_address=get_client_ip(request),
    )
    return {"assistant_id": assistant_id, "course_ids": course_ids}
