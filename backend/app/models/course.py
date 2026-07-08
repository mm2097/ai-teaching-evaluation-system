"""课程与选修模型。对应设计文档 4.2.4、4.2.5 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Course(SQLModel, table=True):
    """课程信息表 course。"""

    __tablename__ = "course"

    course_id: Optional[int] = Field(default=None, primary_key=True)
    course_code: str = Field(max_length=32, unique=True, index=True)
    course_name: str = Field(max_length=64)
    teacher_id: int = Field(foreign_key="teacher.teacher_id", index=True)
    semester: str = Field(max_length=32)
    college: str = Field(max_length=64)
    credit: Optional[float] = Field(default=None)
    status: int = Field(default=0)  # 0=未开始, 1=进行中, 2=已结束
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class CourseStudent(SQLModel, table=True):
    """课程选修表 course_student。"""

    __tablename__ = "course_student"

    enroll_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    enroll_time: datetime = Field(default_factory=datetime.now)
    status: int = Field(default=1)  # 0=已退选, 1=正常选修
    create_time: datetime = Field(default_factory=datetime.now)
