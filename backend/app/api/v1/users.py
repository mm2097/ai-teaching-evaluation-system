"""用户管理接口。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import SysUser, UserCreate, UserRead, UserUpdate

router = APIRouter()


@router.get("/users", response_model=list[UserRead], tags=["用户管理"])
def list_users(session: Session = Depends(get_session)) -> list[SysUser]:
    """列出所有用户。"""
    return session.exec(select(SysUser)).all()


@router.post("/users", response_model=UserRead, status_code=201, tags=["用户管理"])
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> SysUser:
    """创建用户。用户名重复返回 400。"""
    if session.exec(select(SysUser).where(SysUser.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = SysUser(**payload.model_dump())
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserRead, tags=["用户管理"])
def get_user(user_id: int, session: Session = Depends(get_session)) -> SysUser:
    """查询单个用户。不存在返回 404。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/users/{user_id}", response_model=UserRead, tags=["用户管理"])
def update_user(
    user_id: int, payload: UserUpdate, session: Session = Depends(get_session)
) -> SysUser:
    """更新用户(只改传入的字段)。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204, tags=["用户管理"])
def delete_user(user_id: int, session: Session = Depends(get_session)) -> None:
    """删除用户。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    session.delete(user)
    session.commit()
