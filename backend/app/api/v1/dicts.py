"""基础字典 API：班级、教师、学院、学期。"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import ClassInfo, Teacher, Course, Student

router = APIRouter()


@router.get("/classes", tags=["字典"])
def list_classes(
    college: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出班级。"""
    stmt = select(ClassInfo)
    if college:
        stmt = stmt.where(ClassInfo.college == college)
    classes = session.exec(stmt).all()
    return [
        {"class_id": c.class_id, "class_name": c.class_name, "college": c.college, "enroll_year": c.enroll_year}
        for c in classes
    ]


@router.get("/classes/{class_id}/students", tags=["字典"])
def get_class_students(class_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """获取班级内学生列表。"""
    students = session.exec(select(Student).where(Student.class_id == class_id)).all()
    return [
        {"student_id": s.student_id, "student_no": s.student_no, "real_name": s.real_name}
        for s in students
    ]


@router.get("/teachers", tags=["字典"])
def list_teachers(
    college: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出教师。"""
    stmt = select(Teacher)
    if college:
        stmt = stmt.where(Teacher.college == college)
    teachers = session.exec(stmt).all()
    return [
        {
            "teacher_id": t.teacher_id, "teacher_no": t.teacher_no,
            "real_name": t.real_name, "title": t.title, "college": t.college,
        }
        for t in teachers
    ]


@router.get("/dictionaries/departments", tags=["字典"])
def list_departments(session: Session = Depends(get_session)) -> list[str]:
    """列出所有学院（从课程和教师表中提取去重值）。"""
    from sqlalchemy import union
    stmt = union(
        select(Course.college).distinct(),
        select(Teacher.college).distinct(),
    )
    results = session.exec(stmt).all()
    return sorted(set(r for r in results if r))


@router.get("/dictionaries/semesters", tags=["字典"])
def list_semesters(session: Session = Depends(get_session)) -> list[str]:
    """列出所有学期（从课程表中提取去重值）。"""
    results = session.exec(select(Course.semester).distinct()).all()
    return sorted(set(r for r in results if r))
