"""课堂互动记录模型。对应设计文档 4.3.2 节。"""
from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class InteractionRecord(SQLModel, table=True):
    """课堂互动记录表 interaction_record。"""

    __tablename__ = "interaction_record"

    interaction_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    interaction_date: date
    type: int  # 1=课堂提问, 2=小组讨论, 3=作业提交, 4=课堂测验
    score: float = Field(default=0)
    remark: Optional[str] = Field(default=None, max_length=255)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
