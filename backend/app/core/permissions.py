"""Role-based permission dependencies shared by API modules."""
from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import Student, SysRole, SysUser


def get_role_code(current_user: SysUser, session: Session) -> str:
    """Return the current user's role code or reject an invalid role binding."""
    role = session.get(SysRole, current_user.role_id)
    if not role:
        raise HTTPException(status_code=403, detail="当前账号未关联有效角色")
    return role.role_code


def ensure_roles(
    current_user: SysUser,
    session: Session,
    *allowed_roles: str,
) -> str:
    """Ensure the current user has one of the allowed roles."""
    role_code = get_role_code(current_user, session)
    if role_code not in allowed_roles:
        raise HTTPException(status_code=403, detail="当前角色无权访问该功能")
    return role_code


def require_roles(*allowed_roles: str) -> Callable[..., SysUser]:
    """Build a FastAPI dependency that returns an authorized current user."""
    allowed = tuple(allowed_roles)

    def dependency(
        current_user: SysUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> SysUser:
        ensure_roles(current_user, session, *allowed)
        return current_user

    dependency.__name__ = f"require_{'_or_'.join(allowed)}"
    return dependency


require_admin = require_roles("admin")
require_teacher = require_roles("teacher")
require_assistant = require_roles("assistant")
require_teaching_staff = require_roles("teacher", "assistant")
require_teaching_user = require_roles("teacher", "student")


def resolve_student_scope(
    session: Session,
    current_user: SysUser,
    requested_student_id: int | None,
) -> int | None:
    """学生角色强制收敛为本人 student_id（成绩/考勤等个人数据接口用）。

    - teacher/admin：按请求参数返回（None 表示不过滤）
    - student：参数缺省时返回本人 id；传他人 id 或未绑定学生档案时 403
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""
    if role_code in ("teacher", "admin"):
        return requested_student_id
    own = session.exec(
        select(Student).where(Student.user_id == current_user.user_id)
    ).first()
    if not own or own.student_id is None:
        raise HTTPException(status_code=403, detail="当前账号未关联学生档案")
    if requested_student_id is not None and requested_student_id != own.student_id:
        raise HTTPException(status_code=403, detail="学生仅可查看本人的数据")
    return own.student_id
