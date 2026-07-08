"""学生管理 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Student, CourseStudent

router = APIRouter()


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

    return [
        {
            "student_id": s.student_id,
            "student_no": s.student_no,
            "real_name": s.real_name,
            "gender": s.gender,
            "class_id": s.class_id,
            "phone": s.phone,
            "email": s.email,
        }
        for s in students
    ]


@router.get("/students/{student_id}", tags=["学生管理"])
def get_student(student_id: int, session: Session = Depends(get_session)) -> dict:
    """查询单个学生。"""
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {
        "student_id": student.student_id,
        "student_no": student.student_no,
        "real_name": student.real_name,
        "gender": student.gender,
        "class_id": student.class_id,
        "phone": student.phone,
        "email": student.email,
    }
