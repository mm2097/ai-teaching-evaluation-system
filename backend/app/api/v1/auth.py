"""认证接口:登录、修改本人密码。"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.core.database import get_session
from app.core.operation_log import get_client_ip, get_current_user, save_operation_log
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
    student_no: str | None = None
    class_id: int | None = None
    student_phone: str | None = None
    student_email: str | None = None
    # 教师
    teacher_id: int | None = None
    college: str | None = None
    title: str | None = None
    teacher_phone: str | None = None
    teacher_email: str | None = None


class LoginResponse(SQLModel):
    token: str
    user: LoginUser


class ChangePasswordRequest(SQLModel):
    """修改密码请求体。"""
    old_password: str
    new_password: str


class UpdateContactRequest(SQLModel):
    """学生/教师修改本人联系方式请求体（手机号/邮箱可空）。"""
    phone: str | None = None
    email: str | None = None


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

    # 学生登录时附加 student_id / student_no / class_id / 联系方式
    student_id: int | None = None
    student_no: str | None = None
    class_id: int | None = None
    student_phone: str | None = None
    student_email: str | None = None
    if role_code == "student":
        student = session.exec(select(Student).where(Student.user_id == user.user_id)).first()
        if student:
            student_id = student.student_id
            student_no = student.student_no
            class_id = student.class_id
            student_phone = student.phone
            student_email = student.email

    # 教师登录时附加 teacher_id / college / title / 联系方式
    teacher_id: int | None = None
    college: str | None = None
    title: str | None = None
    teacher_phone: str | None = None
    teacher_email: str | None = None
    if role_code == "teacher":
        teacher = session.exec(select(Teacher).where(Teacher.user_id == user.user_id)).first()
        if teacher:
            teacher_id = teacher.teacher_id
            college = teacher.college
            title = teacher.title
            teacher_phone = teacher.phone
            teacher_email = teacher.email

    token = create_token(user.user_id, user.username)
    return LoginResponse(
        token=token,
        user=LoginUser(
            user_id=user.user_id,
            username=user.username,
            real_name=user.real_name,
            role_code=role_code,
            student_id=student_id,
            student_no=student_no,
            class_id=class_id,
            student_phone=student_phone,
            student_email=student_email,
            teacher_id=teacher_id,
            college=college,
            title=title,
            teacher_phone=teacher_phone,
            teacher_email=teacher_email,
        ),
    )


@router.post("/password/change", tags=["认证"])
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """修改本人登录密码。校验原密码后写入新密码哈希，并记录操作日志。"""
    if not verify_password(payload.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="原密码错误")
    new_password = payload.new_password.strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于 6 位")
    if verify_password(new_password, current_user.password):
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    current_user.password = hash_password(new_password)
    current_user.update_time = datetime.now()
    session.add(current_user)
    session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="个人设置",
        operation="修改密码",
        content=f"用户 {current_user.username} 修改登录密码",
        ip_address=get_client_ip(request),
    )
    return {"message": "密码修改成功"}


@router.put("/profile/contact", tags=["认证"])
def update_contact(
    payload: UpdateContactRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """学生/教师修改本人联系方式（手机号/邮箱）。学生、教师仅可更改手机号、邮箱、密码。"""
    student = session.exec(select(Student).where(Student.user_id == current_user.user_id)).first()
    teacher = None
    if not student:
        teacher = session.exec(select(Teacher).where(Teacher.user_id == current_user.user_id)).first()
    if not student and not teacher:
        raise HTTPException(status_code=403, detail="仅学生和教师可修改联系方式")
    target = student if student else teacher
    # 传空串表示清空，传 null 表示不改动
    if payload.phone is not None:
        target.phone = (payload.phone or "").strip() or None
    if payload.email is not None:
        target.email = (payload.email or "").strip() or None
    target.update_time = datetime.now()
    session.add(target)
    session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="个人设置",
        operation="修改联系方式",
        content=f"{'学生' if student else '教师'} {current_user.username} 更新手机号/邮箱",
        ip_address=get_client_ip(request),
    )
    return {"phone": target.phone, "email": target.email}
