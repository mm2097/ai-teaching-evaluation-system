"""教学数据聚合接口：合并成绩、考勤等数据供数据管理页面展示。"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import ScoreRecord, AttendanceRecord, Course, Student, CourseStudent

router = APIRouter()


@router.get("/teaching-data", tags=["教学数据"])
def get_teaching_data(session: Session = Depends(get_session)) -> list[dict]:
    """返回所有教学数据（成绩 + 考勤），供数据管理页面展示。"""
    result: list[dict] = []
    row_id = 1

    # 成绩记录
    scores = session.exec(select(ScoreRecord)).all()
    for s in scores:
        course = session.get(Course, s.course_id)
        student = session.get(Student, s.student_id)
        if not course or not student:
            continue
        result.append({
            "id": row_id,
            "dataType": "score",
            "studentId": student.student_no,
            "studentName": student.real_name,
            "courseId": course.course_code,
            "courseName": course.course_name,
            "semester": course.semester,
            "score": s.score,
            "attendance": None,
            "homework": None,
            "sourceFileName": "seed_data",
            "classId": student.class_id,
            "deptId": 1,
            "majorId": 0,
        })
        row_id += 1

    # 考勤记录
    attendances = session.exec(select(AttendanceRecord)).all()
    status_map = {0: "正常", 1: "迟到", 2: "早退", 3: "缺勤", 4: "请假"}
    for a in attendances:
        course = session.get(Course, a.course_id)
        student = session.get(Student, a.student_id)
        if not course or not student:
            continue
        result.append({
            "id": row_id,
            "dataType": "attendance",
            "studentId": student.student_no,
            "studentName": student.real_name,
            "courseId": course.course_code,
            "courseName": course.course_name,
            "semester": course.semester,
            "score": None,
            "attendance": status_map.get(a.status, "正常"),
            "homework": None,
            "sourceFileName": "seed_data",
            "classId": student.class_id,
            "deptId": 1,
            "majorId": 0,
        })
        row_id += 1

    return result
