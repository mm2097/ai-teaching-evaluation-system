"""认证接口:登录。"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.core.database import get_session
from app.models import User

router = APIRouter()


class LoginRequest(SQLModel):
    username: str
    password: str


class LoginUser(SQLModel):
    id: int
    username: str
    name: str
    role: str
    department: str


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
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if not user.status:
        raise HTTPException(status_code=403, detail="账号已禁用,请联系管理员")
    token = create_token(user.id, user.username)
    return LoginResponse(
        token=token,
        user=LoginUser(
            id=user.id,
            username=user.username,
            name=user.name,
            role=user.role,
            department=user.department,
        ),
    )
