"""用户管理接口。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_client_ip, get_current_user, save_operation_log
from app.core.security import hash_password
from app.models import SysUser, SysRole, UserCreate, UserRead, UserUpdate

router = APIRouter()


def _check_admin_protection(session: Session, target_user: SysUser, current_user: SysUser) -> None:
    """管理员保护：禁止管理员禁用/降级另一个管理员。"""
    target_role = session.get(SysRole, target_user.role_id)
    if target_role and target_role.role_code == "admin":
        current_role = session.get(SysRole, current_user.role_id)
        if current_role and current_role.role_code == "admin":
            raise HTTPException(status_code=403, detail="管理员不能操作其他管理员账号")


@router.get("/users", response_model=list[UserRead], tags=["用户管理"])
def list_users(session: Session = Depends(get_session)) -> list[SysUser]:
    """列出所有用户。"""
    return session.exec(select(SysUser)).all()


@router.post("/users", response_model=UserRead, status_code=201, tags=["用户管理"])
def create_user(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    """创建用户。用户名重复返回 400。"""
    if session.exec(select(SysUser).where(SysUser.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    # 不允许创建已禁用的系统管理员账号，防止死锁
    if payload.status == 0:
        role = session.get(SysRole, payload.role_id)
        if role and role.role_code == "admin":
            raise HTTPException(status_code=403, detail="不允许创建已禁用的系统管理员账号")
    user_data = payload.model_dump()
    user_data["password"] = hash_password(user_data["password"])
    user = SysUser(**user_data)
    session.add(user)
    session.commit()
    session.refresh(user)
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="用户管理",
        operation="新增",
        content=f"创建用户：{user.username}",
        ip_address=get_client_ip(request),
    )
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
    user_id: int,
    payload: UserUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    """更新用户(只改传入的字段)。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 管理员保护：禁止禁用/降级其他管理员
    if "status" in payload.model_dump(exclude_unset=True) or "role_id" in payload.model_dump(exclude_unset=True):
        _check_admin_protection(session, user, current_user)
    updates = payload.model_dump(exclude_unset=True)
    # 系统管理员的启用/禁用状态不允许任何人员修改（包括自己），防止死锁
    if "status" in updates:
        role = session.get(SysRole, user.role_id)
        if role and role.role_code == "admin":
            raise HTTPException(status_code=403, detail="不允许启用/禁用系统管理员账号")
    if "password" in updates:
        updates["password"] = hash_password(updates["password"])
    for field, value in updates.items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="用户管理",
        operation="编辑",
        content=f"更新用户：{user.username}",
        ip_address=get_client_ip(request),
    )
    return user


@router.delete("/users/{user_id}", status_code=204, tags=["用户管理"])
def delete_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> None:
    """删除用户。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 管理员保护：禁止删除其他管理员
    _check_admin_protection(session, user, current_user)
    session.delete(user)
    session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="用户管理",
        operation="删除",
        content=f"删除用户：{user.username}",
        ip_address=get_client_ip(request),
    )
