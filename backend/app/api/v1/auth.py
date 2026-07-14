"""认证接口:登录。"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.core.database import get_session
from app.core.security import hash_password, password_needs_rehash, verify_password
from app.models import SysUser, SysRole, LoginRequest
from app.models.student import Student
from app.models.teacher import Teacher

router = APIRouter()
_DUMMY_PASSWORD_HASH = hash_password("invalid-login-password")


class LoginUser(SQLModel):
    user_id: int
    username: str
    real_name: str
    role_code: str
    # 学生
    student_id: int | None = None
    class_id: int | None = None
    # 教师
    teacher_id: int | None = None
    college: str | None = None
    title: str | None = None


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
    stored_password = user.password if user else _DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, stored_password) or not user:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已禁用,请联系管理员")
    if password_needs_rehash(user.password):
        user.password = hash_password(payload.password)
        user.update_time = datetime.now()
        session.add(user)
        session.commit()

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

    # 教师登录时附加 teacher_id / college / title
    teacher_id: int | None = None
    college: str | None = None
    title: str | None = None
    if role_code == "teacher":
        teacher = session.exec(select(Teacher).where(Teacher.user_id == user.user_id)).first()
        if teacher:
            teacher_id = teacher.teacher_id
            college = teacher.college
            title = teacher.title

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
            teacher_id=teacher_id,
            college=college,
            title=title,
        ),
    )
