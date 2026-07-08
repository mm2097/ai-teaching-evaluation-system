"""考勤记录模型。对应设计文档 4.3.1 节。"""
from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AttendanceRecord(SQLModel, table=True):
    """考勤记录表 attendance_record。

    联合唯一索引: (course_id, student_id, attendance_date)
    """

    __tablename__ = "attendance_record"

    attendance_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    attendance_date: date
    status: int = Field(default=0)  # 0=出勤, 1=迟到, 2=早退, 3=缺勤, 4=请假
    remark: Optional[str] = Field(default=None, max_length=255)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
