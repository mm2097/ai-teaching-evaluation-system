"""Role-based permission dependencies shared by API modules."""
from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import SysRole, SysUser


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
require_teaching_user = require_roles("teacher", "student")
