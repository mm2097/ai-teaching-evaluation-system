"""学生管理 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_client_ip, save_operation_log
from app.core.permissions import require_admin
from app.models import (
    ClassInfo,
    CourseStudent,
    Student,
    StudentCreate,
    StudentUpdate,
    SysRole,
    SysUser,
)

router = APIRouter()


def _serialize_student(session: Session, student: Student) -> dict:
    class_info = session.get(ClassInfo, student.class_id)
    return {
        "student_id": student.student_id,
        "student_no": student.student_no,
        "real_name": student.real_name,
        "gender": student.gender,
        "class_id": student.class_id,
        "class_name": class_info.class_name if class_info else "",
        "user_id": student.user_id,
        "phone": student.phone,
        "email": student.email,
    }


@router.get("/students", tags=["学生管理"])
def list_students(
    class_id: int | None = Query(default=None, description="按班级 ID 筛选"),
    course_id: int | None = Query(default=None, description="按课程筛选（查选修该课的学生）"),
    keyword: str | None = Query(default=None, description="模糊搜索：姓名或学号"),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出学生。"""
    if course_id:
        enrollments = session.exec(
            select(CourseStudent).where(CourseStudent.course_id == course_id)
        ).all()
        student_ids = [e.student_id for e in enrollments]
        if not student_ids:
            return []
        stmt = select(Student).where(Student.student_id.in_(student_ids))  # type: ignore[attr-defined]
    else:
        stmt = select(Student)

    if class_id:
        stmt = stmt.where(Student.class_id == class_id)  # type: ignore[arg-type]

    students = session.exec(stmt).all()

    if keyword:
        kw = keyword.lower()
        students = [
            s for s in students
            if kw in s.real_name.lower() or kw in s.student_no.lower()
        ]

    return [_serialize_student(session, s) for s in students]


@router.post("/students", status_code=201, tags=["学生管理"])
def create_student(
    payload: StudentCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """为学生账号绑定班级档案（管理员）。"""
    user = session.get(SysUser, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    role = session.get(SysRole, user.role_id)
    if not role or role.role_code != "student":
        raise HTTPException(status_code=400, detail="只能为学生角色账号绑定班级")
    if session.exec(select(Student).where(Student.user_id == payload.user_id)).first():
        raise HTTPException(status_code=400, detail="该账号已绑定学生档案")
    if not session.get(ClassInfo, payload.class_id):
        raise HTTPException(status_code=400, detail="所属班级不存在")
    student_no = (payload.student_no or user.username).strip()
    if session.exec(select(Student).where(Student.student_no == student_no)).first():
        raise HTTPException(status_code=400, detail="学号已存在")
    student = Student(
        student_no=student_no,
        real_name=payload.real_name or user.real_name,
        gender=payload.gender,
        class_id=payload.class_id,
        user_id=payload.user_id,
        phone=payload.phone,
        email=payload.email,
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="学生管理",
        operation="新增",
        content=f"绑定学生档案：{student.student_no}",
        ip_address=get_client_ip(request),
    )
    return _serialize_student(session, student)


@router.get("/students/{student_id}", tags=["学生管理"])
def get_student(student_id: int, session: Session = Depends(get_session)) -> dict:
    """查询单个学生。"""
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return _serialize_student(session, student)


@router.put("/students/{student_id}", tags=["学生管理"])
def update_student(
    student_id: int,
    payload: StudentUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> dict:
    """更新学生信息（含班级分配）。"""
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    updates = payload.model_dump(exclude_unset=True)
    if "class_id" in updates and not session.get(ClassInfo, updates["class_id"]):
        raise HTTPException(status_code=400, detail="所属班级不存在")
    for field, value in updates.items():
        setattr(student, field, value)
    session.add(student)
    session.commit()
    session.refresh(student)
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="学生管理",
        operation="编辑",
        content=f"更新学生：{student.student_no}",
        ip_address=get_client_ip(request),
    )
    return _serialize_student(session, student)


@router.delete("/students/{student_id}", status_code=204, tags=["学生管理"])
def delete_student(
    student_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(require_admin),
) -> None:
    """删除学生档案（有选课数据时拒绝）。"""
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    enrolled = session.exec(
        select(CourseStudent).where(CourseStudent.student_id == student_id)
    ).first()
    if enrolled:
        raise HTTPException(status_code=400, detail="该学生已有选课数据，无法删除")
    student_no = student.student_no
    session.delete(student)
    session.commit()
    save_operation_log(
        session,
        user_id=current_user.user_id,
        module="学生管理",
        operation="删除",
        content=f"删除学生档案：{student_no}",
        ip_address=get_client_ip(request),
    )
