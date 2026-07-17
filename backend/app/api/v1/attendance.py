"""考勤记录 API。"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.permissions import require_teaching_user
from app.models import AttendanceRecord, Student, Course

router = APIRouter(dependencies=[Depends(require_teaching_user)])


@router.get("/attendance-records", tags=["考勤管理"])
def list_attendance(
    course_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """列出考勤记录。"""
    stmt = select(AttendanceRecord)
    if course_id:
        stmt = stmt.where(AttendanceRecord.course_id == course_id)
    if student_id:
        stmt = stmt.where(AttendanceRecord.student_id == student_id)
    records = session.exec(stmt).all()

    status_map = {0: "出勤", 1: "迟到", 2: "早退", 3: "缺勤", 4: "请假"}
    return [
        {
            "attendance_id": r.attendance_id,
            "course_id": r.course_id,
            "student_id": r.student_id,
            "attendance_date": r.attendance_date.isoformat() if r.attendance_date else None,
            "status": status_map.get(r.status, "未知"),
            "status_code": r.status,
            "remark": r.remark,
        }
        for r in records
    ]
