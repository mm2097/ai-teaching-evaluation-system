"""课程管理 API。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Course

router = APIRouter()


@router.get("/courses", tags=["课程管理"])
def list_courses(
    teacher_id: int | None = Query(default=None, description="按教师 ID 筛选"),
    college: str | None = Query(default=None, description="按学院筛选"),
    semester: str | None = Query(default=None, description="按学期筛选"),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出课程，支持按教师/学院/学期筛选。"""
    stmt = select(Course)
    if teacher_id:
        stmt = stmt.where(Course.teacher_id == teacher_id)
    if college:
        stmt = stmt.where(Course.college == college)
    if semester:
        stmt = stmt.where(Course.semester == semester)
    courses = session.exec(stmt).all()
    return [
        {
            "course_id": c.course_id,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "teacher_id": c.teacher_id,
            "semester": c.semester,
            "college": c.college,
            "credit": c.credit,
            "status": c.status,
        }
        for c in courses
    ]


@router.get("/courses/{course_id}", tags=["课程管理"])
def get_course(course_id: int, session: Session = Depends(get_session)) -> dict:
    """查询单个课程。"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return {
        "course_id": course.course_id,
        "course_code": course.course_code,
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "semester": course.semester,
        "college": course.college,
        "credit": course.credit,
        "status": course.status,
    }


@router.post("/courses", status_code=201, tags=["课程管理"])
def create_course(
    course_code: str = Query(...),
    course_name: str = Query(...),
    teacher_id: int = Query(...),
    semester: str = Query(...),
    college: str = Query(...),
    credit: float | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """创建课程。"""
    if session.exec(select(Course).where(Course.course_code == course_code)).first():
        raise HTTPException(status_code=400, detail="课程编号已存在")
    course = Course(
        course_code=course_code, course_name=course_name,
        teacher_id=teacher_id, semester=semester, college=college,
        credit=credit, status=0,
    )
    session.add(course)
    session.commit()
    session.refresh(course)
    return {"course_id": course.course_id, "course_name": course.course_name}


@router.put("/courses/{course_id}", tags=["课程管理"])
def update_course(
    course_id: int,
    course_name: str | None = Query(default=None),
    teacher_id: int | None = Query(default=None),
    semester: str | None = Query(default=None),
    credit: float | None = Query(default=None),
    status: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """更新课程(只改传入字段)。"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if course_name is not None:
        course.course_name = course_name
    if teacher_id is not None:
        course.teacher_id = teacher_id
    if semester is not None:
        course.semester = semester
    if credit is not None:
        course.credit = credit
    if status is not None:
        course.status = status
    session.add(course)
    session.commit()
    session.refresh(course)
    return {"course_id": course.course_id, "course_name": course.course_name}


@router.delete("/courses/{course_id}", status_code=204, tags=["课程管理"])
def delete_course(course_id: int, session: Session = Depends(get_session)) -> None:
    """删除课程。"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    session.delete(course)
    session.commit()
