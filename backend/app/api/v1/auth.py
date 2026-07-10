"""认证接口:登录。"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.core.database import get_session
from app.models import SysUser, SysRole, LoginRequest
from app.models.student import Student

router = APIRouter()


class LoginUser(SQLModel):
    user_id: int
    username: str
    real_name: str
    role_code: str
    student_id: int | None = None
    class_id: int | None = None


class LoginResponse(SQLModel):
    token: str
    user: LoginUser


def create_token(user_id: int, username: str) -> str:
    """签发 JWT。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=settings.TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@router.post("/login", response_model=LoginResponse, tags=["认证"])
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> LoginResponse:
    """账号密码登录。成功返回 JWT + 用户信息;密码错返回 401,账号禁用返回 403。"""
    user = session.exec(select(SysUser).where(SysUser.username == payload.username)).first()
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已禁用,请联系管理员")

    role = session.get(SysRole, user.role_id)
    role_code = role.role_code if role else ""

    # 学生登录时附加 student_id / class_id
    student_id: int | None = None
    class_id: int | None = None
    if role_code == "student":
        student = session.exec(select(Student).where(Student.user_id == user.user_id)).first()
        if student:
            student_id = student.student_id
            class_id = student.class_id

    token = create_token(user.user_id, user.username)
    return LoginResponse(
        token=token,
        user=LoginUser(
            user_id=user.user_id,
            username=user.username,
            real_name=user.real_name,
            role_code=role_code,
            student_id=student_id,
            class_id=class_id,
        ),
    )
