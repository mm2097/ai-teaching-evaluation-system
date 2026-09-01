"""用户管理接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_client_ip, save_operation_log
from app.core.permissions import require_admin
from app.core.security import hash_password
from app.models import (
    ClassInfo,
    Course,
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


def _get_teacher(session: Session, user_id: int | None) -> Teacher | None:
    if not user_id:
        return None
    return session.exec(select(Teacher).where(Teacher.user_id == user_id)).first()


def _ensure_student_profile(
    session: Session,
    user: SysUser,
    class_id: int,
    student_no: str | None = None,
    gender: int | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> Student:
    """把班级等学生表字段同步到 student 表，不改 sys_user。

    - 学号：未提供时新建默认与账号相同，已有档案则保留原学号
    - 性别：新建默认男(1)，已有档案未提供时保留原值
    - 手机号/邮箱：可空，提供时更新（空串视为清空）
    """
    class_info = session.get(ClassInfo, class_id)
    if not class_info:
        raise HTTPException(status_code=400, detail="所属班级不存在")
    resolved_no = (student_no or "").strip()
    student = _get_student(session, user.user_id)
    if student:
        if resolved_no and resolved_no != student.student_no:
            occupied = session.exec(
                select(Student).where(Student.student_no == resolved_no)
            ).first()
            if occupied and occupied.user_id != user.user_id:
                raise HTTPException(status_code=400, detail=f"学号 {resolved_no} 已被占用")
            student.student_no = resolved_no
        student.class_id = class_id
        student.real_name = user.real_name
        if gender is not None:
            student.gender = gender
        if phone is not None:
            student.phone = phone.strip() or None
        if email is not None:
            student.email = email.strip() or None
        student.update_time = datetime.now()
        session.add(student)
        return student
    # 新建学生档案
    final_no = resolved_no or user.username
    occupied = session.exec(select(Student).where(Student.student_no == final_no)).first()
    if occupied and occupied.user_id != user.user_id:
        raise HTTPException(status_code=400, detail=f"学号 {final_no} 已被占用")
    student = Student(
        student_no=final_no,
        real_name=user.real_name,
        class_id=class_id,
        user_id=user.user_id,
        gender=1 if gender is None else gender,  # 默认男
        phone=(phone or "").strip() or None,
        email=(email or "").strip() or None,
    )
    session.add(student)
    return student


def _ensure_teacher_profile(
    session: Session,
    user: SysUser,
    teacher_no: str | None = None,
    title: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> Teacher:
    """把教工号等教师表字段同步到 teacher 表，不改 sys_user。

    - 教工号：未提供时新建默认与账号相同，已有档案则保留原教工号
    - 职称/手机号/邮箱：可空，提供时更新（空串视为清空）
    - 学院：取用户表学院，回退默认计算机学院
    """
    resolved_no = (teacher_no or "").strip()
    teacher = _get_teacher(session, user.user_id)
    if teacher:
        if resolved_no and resolved_no != teacher.teacher_no:
            occupied = session.exec(
                select(Teacher).where(Teacher.teacher_no == resolved_no)
            ).first()
            if occupied and occupied.user_id != user.user_id:
                raise HTTPException(status_code=400, detail=f"教工号 {resolved_no} 已被占用")
            teacher.teacher_no = resolved_no
        teacher.real_name = user.real_name
        teacher.college = user.college or teacher.college or "计算机学院"
        if title is not None:
            teacher.title = title.strip() or None
        if phone is not None:
            teacher.phone = phone.strip() or None
        if email is not None:
            teacher.email = email.strip() or None
        teacher.update_time = datetime.now()
        session.add(teacher)
        return teacher
    # 新建教师档案
    final_no = resolved_no or user.username
    occupied = session.exec(select(Teacher).where(Teacher.teacher_no == final_no)).first()
    if occupied and occupied.user_id != user.user_id:
        raise HTTPException(status_code=400, detail=f"教工号 {final_no} 已被占用")
    teacher = Teacher(
        teacher_no=final_no,
        real_name=user.real_name,
        user_id=user.user_id,
        college=user.college or "计算机学院",
        title=(title or "").strip() or None,
        phone=(phone or "").strip() or None,
        email=(email or "").strip() or None,
    )
    session.add(teacher)
    return teacher


def _serialize_user(session: Session, user: SysUser) -> dict:
    """Return management fields without exposing password hashes."""
    role = session.get(SysRole, user.role_id)
    role_code = role.role_code if role else ""
    department = user.college or ""
    student = _get_student(session, user.user_id)
    teacher = _get_teacher(session, user.user_id)
    class_info = session.get(ClassInfo, student.class_id) if student else None
    if not department and role_code == "teacher":
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
        "student_no": student.student_no if student else "",
        "gender": student.gender if student else None,
        "teacher_no": teacher.teacher_no if teacher else "",
        "title": teacher.title if teacher else "",
        "phone": student.phone if student else (teacher.phone if teacher else ""),
        "email": student.email if student else (teacher.email if teacher else ""),
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
    student_no = user_data.pop("student_no", None)
    gender = user_data.pop("gender", None)
    teacher_no = user_data.pop("teacher_no", None)
    title = user_data.pop("title", None)
    phone = user_data.pop("phone", None)
    email = user_data.pop("email", None)
    role = session.get(SysRole, payload.role_id)
    role_code = role.role_code if role else ""
    if role_code == "student":
        if not class_id:
            raise HTTPException(status_code=400, detail="学生用户必须选择所属班级")
        if not session.get(ClassInfo, class_id):
            raise HTTPException(status_code=400, detail="所属班级不存在")
        # 学号唯一性预校验，避免用户表写入成功而学生表写入失败
        resolved_no = (student_no or "").strip() or payload.username
        occupied = session.exec(select(Student).where(Student.student_no == resolved_no)).first()
        if occupied:
            raise HTTPException(status_code=400, detail=f"学号 {resolved_no} 已被占用")
    if role_code == "teacher":
        # 教工号唯一性预校验，避免用户表写入成功而教师表写入失败
        resolved_no = (teacher_no or "").strip() or payload.username
        occupied = session.exec(select(Teacher).where(Teacher.teacher_no == resolved_no)).first()
        if occupied:
            raise HTTPException(status_code=400, detail=f"教工号 {resolved_no} 已被占用")
    user_data["password"] = hash_password(user_data["password"])
    college = (user_data.get("college") or "").strip()
    user_data["college"] = college or "计算机学院"
    user = SysUser(**user_data)
    session.add(user)
    session.flush()  # 先生成 user_id 供学生/教师档案引用，最终一并提交保证原子性
    if role_code == "student" and class_id:
        # 同步写入学生表：学号默认与账号相同，性别默认男，手机号/邮箱可空
        _ensure_student_profile(
            session, user, class_id,
            student_no=student_no, gender=gender, phone=phone, email=email,
        )
    if role_code == "teacher":
        # 同步写入教师表：教工号默认与账号相同，职称/手机号/邮箱可空
        _ensure_teacher_profile(
            session, user,
            teacher_no=teacher_no, title=title, phone=phone, email=email,
        )
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
    student_no = updates.pop("student_no", None)
    gender = updates.pop("gender", None)
    teacher_no = updates.pop("teacher_no", None)
    title = updates.pop("title", None)
    phone = updates.pop("phone", None)
    email = updates.pop("email", None)
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
    # 学生角色：同步学生表（班级/学号/性别/联系方式任一有变更时），
    # 先于提交执行，校验失败（如学号冲突）时不产生半成品数据
    if pending_code == "student":
        student = _get_student(session, user.user_id)
        if student and (
            class_id is not None or student_no is not None
            or gender is not None or phone is not None or email is not None
        ):
            _ensure_student_profile(
                session, user,
                class_id if class_id is not None else student.class_id,
                student_no=student_no, gender=gender, phone=phone, email=email,
            )
    # 教师角色：同步教师表（教工号/职称/学院/联系方式），
    # 档案缺失时自动补建，修复历史遗留的"只有用户表无教师表"数据
    if pending_code == "teacher":
        _ensure_teacher_profile(
            session, user,
            teacher_no=teacher_no, title=title, phone=phone, email=email,
        )
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
    teacher = _get_teacher(session, user.user_id)
    if teacher:
        taught = session.exec(
            select(Course).where(Course.teacher_id == teacher.teacher_id)
        ).first()
        if taught:
            raise HTTPException(status_code=400, detail="该教师已有授课课程数据，无法删除账号")
        session.delete(teacher)
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
