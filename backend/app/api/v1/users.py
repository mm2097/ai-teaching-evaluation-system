"""用户管理接口。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_client_ip, save_operation_log
from app.core.permissions import require_admin
from app.core.security import hash_password
from app.models import (
    ClassInfo,
    CourseStudent,
    Student,
    SysRole,
    SysUser,
    Teacher,
    UserCreate,
    UserUpdate,
)

router = APIRouter()


def _check_admin_protection(session: Session, target_user: SysUser, current_user: SysUser) -> None:
    """管理员保护：禁止管理员禁用/降级另一个管理员。"""
    target_role = session.get(SysRole, target_user.role_id)
    if target_role and target_role.role_code == "admin":
        current_role = session.get(SysRole, current_user.role_id)
        if current_role and current_role.role_code == "admin":
            raise HTTPException(status_code=403, detail="管理员不能操作其他管理员账号")


def _get_student(session: Session, user_id: int | None) -> Student | None:
    if not user_id:
        return None
    return session.exec(select(Student).where(Student.user_id == user_id)).first()


def _ensure_student_profile(session: Session, user: SysUser, class_id: int) -> Student:
    """把班级写到 student 表，不改 sys_user。"""
    class_info = session.get(ClassInfo, class_id)
    if not class_info:
        raise HTTPException(status_code=400, detail="所属班级不存在")
    student = _get_student(session, user.user_id)
    if student:
        student.class_id = class_id
        student.real_name = user.real_name
        session.add(student)
        return student
    student_no = user.username
    occupied = session.exec(select(Student).where(Student.student_no == student_no)).first()
    if occupied:
        student_no = f"{user.username}_{user.user_id}"
    student = Student(
        student_no=student_no,
        real_name=user.real_name,
        class_id=class_id,
        user_id=user.user_id,
    )
    session.add(student)
    return student


def _serialize_user(session: Session, user: SysUser) -> dict:
    """Return management fields without exposing password hashes."""
    role = session.get(SysRole, user.role_id)
    role_code = role.role_code if role else ""
    department = user.college or ""
    student = _get_student(session, user.user_id)
    class_info = session.get(ClassInfo, student.class_id) if student else None
    if not department and role_code == "teacher":
        teacher = session.exec(
            select(Teacher).where(Teacher.user_id == user.user_id)
        ).first()
        department = teacher.college if teacher else ""
    elif not department and role_code == "student":
        department = class_info.college if class_info else ""
    elif not department and role_code == "admin":
        department = "系统管理"

    return {
        "user_id": user.user_id,
        "username": user.username,
        "real_name": user.real_name,
        "role_id": user.role_id,
        "role_code": role_code,
        "role_name": role.role_name if role else "",
        "department": department,
        "class_id": student.class_id if student else None,
        "class_name": class_info.class_name if class_info else "",
        "status": user.status,
        "create_time": user.create_time,
    }


@router.get("/roles", tags=["用户管理"])
def list_roles(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> list[dict]:
    """List roles available for account assignment."""
    roles = session.exec(select(SysRole).order_by(SysRole.role_id)).all()
    return [
        {
            "role_id": role.role_id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "description": role.description,
        }
        for role in roles
    ]


@router.get("/users", tags=["用户管理"])
def list_users(
    class_id: int | None = Query(default=None, description="按学生所属班级筛选"),
    role_code: str | None = Query(default=None, description="按角色筛选：admin/teacher/student"),
    status: int | None = Query(default=None, description="按账号状态筛选：0=停用, 1=正常"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> list[dict]:
    """列出用户。可按角色、学生所属班级、账号状态筛选。"""
    stmt = select(SysUser)
    if class_id is not None:
        stmt = stmt.join(Student, Student.user_id == SysUser.user_id).where(  # type: ignore[arg-type]
            Student.class_id == class_id
        )
    if role_code:
        role = session.exec(select(SysRole).where(SysRole.role_code == role_code)).first()
        if role:
            stmt = stmt.where(SysUser.role_id == role.role_id)
    if status is not None:
        stmt = stmt.where(SysUser.status == status)
    users = session.exec(stmt.order_by(SysUser.create_time.desc())).all()
    return [_serialize_user(session, user) for user in users]


@router.post("/users", status_code=201, tags=["用户管理"])
def create_user(
    payload: UserCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """创建用户。用户名重复返回 400。学生必须选择所属班级。"""
    if session.exec(select(SysUser).where(SysUser.username == payload.username)).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if payload.status == 0:
        role = session.get(SysRole, payload.role_id)
        if role and role.role_code == "admin":
            raise HTTPException(status_code=403, detail="不允许创建已禁用的系统管理员账号")
    user_data = payload.model_dump()
    class_id = user_data.pop("class_id", None)
    role = session.get(SysRole, payload.role_id)
    role_code = role.role_code if role else ""
    if role_code == "student":
        if not class_id:
            raise HTTPException(status_code=400, detail="学生用户必须选择所属班级")
        if not session.get(ClassInfo, class_id):
            raise HTTPException(status_code=400, detail="所属班级不存在")
    user_data["password"] = hash_password(user_data["password"])
    college = (user_data.get("college") or "").strip()
    user_data["college"] = college or "计算机学院"
    user = SysUser(**user_data)
    session.add(user)
    session.commit()
    session.refresh(user)
    if role_code == "student" and class_id:
        _ensure_student_profile(session, user, class_id)
        session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="用户管理",
        operation="新增",
        content=f"创建用户：{user.username}",
        ip_address=get_client_ip(request),
    )
    return _serialize_user(session, user)


@router.get("/users/{user_id}", tags=["用户管理"])
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """查询单个用户。不存在返回 404。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _serialize_user(session, user)


@router.put("/users/{user_id}", tags=["用户管理"])
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """更新用户(只改传入的字段)。学生可改所属班级。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if "status" in payload.model_dump(exclude_unset=True) or "role_id" in payload.model_dump(exclude_unset=True):
        _check_admin_protection(session, user, current_user)
    updates = payload.model_dump(exclude_unset=True)
    class_id = updates.pop("class_id", None)
    pending_role_id = updates.get("role_id", user.role_id)
    pending_role = session.get(SysRole, pending_role_id)
    pending_code = pending_role.role_code if pending_role else ""
    if pending_code == "student":
        student = _get_student(session, user.user_id)
        if class_id is None and not student:
            raise HTTPException(status_code=400, detail="学生用户必须选择所属班级")
        if class_id is not None and not session.get(ClassInfo, class_id):
            raise HTTPException(status_code=400, detail="所属班级不存在")
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
    if pending_code == "student" and class_id is not None:
        _ensure_student_profile(session, user, class_id)
        session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="用户管理",
        operation="编辑",
        content=f"更新用户：{user.username}",
        ip_address=get_client_ip(request),
    )
    return _serialize_user(session, user)


@router.delete("/users/{user_id}", status_code=204, tags=["用户管理"])
def delete_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> None:
    """删除用户。已有选课的学生账号拒绝删除。"""
    user = session.get(SysUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _check_admin_protection(session, user, current_user)
    student = _get_student(session, user.user_id)
    if student:
        enrolled = session.exec(
            select(CourseStudent).where(CourseStudent.student_id == student.student_id)
        ).first()
        if enrolled:
            raise HTTPException(status_code=400, detail="该学生已有选课数据，无法删除账号")
        session.delete(student)
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
