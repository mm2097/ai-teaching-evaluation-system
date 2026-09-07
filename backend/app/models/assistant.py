"""助教档案与课程授权模型。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class TeachingAssistant(SQLModel, table=True):
    """助教档案；登录账号仍统一存放在 sys_user。"""

    __tablename__ = "teaching_assistant"

    assistant_id: Optional[int] = Field(default=None, primary_key=True)
    assistant_no: str = Field(max_length=32, unique=True, index=True)
    real_name: str = Field(max_length=32)
    user_id: int = Field(foreign_key="sys_user.user_id", unique=True, index=True)
    college: str = Field(max_length=64)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=64)
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class CourseAssistant(SQLModel, table=True):
    """助教与可维护课程的多对多授权关系。"""

    __tablename__ = "course_assistant"
    __table_args__ = (
        UniqueConstraint("course_id", "assistant_id", name="uq_course_assistant"),
    )

    assignment_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    assistant_id: int = Field(foreign_key="teaching_assistant.assistant_id", index=True)
    create_time: datetime = Field(default_factory=datetime.now)
