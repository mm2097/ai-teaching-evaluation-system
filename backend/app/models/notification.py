"""消息通知模型。对应设计文档 4.6.4 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    """站内通知表 notification（教师 → 学生的预警通知）。"""

    __tablename__ = "notification"

    notification_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: Optional[int] = Field(default=None, foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    # 关联预警记录（弱关联，不设外键：预警刷新会删除未处理记录，通知需保留）
    warning_id: Optional[int] = Field(default=None, index=True)
    title: str = Field(max_length=64)
    content: str = Field(max_length=500)
    is_read: int = Field(default=0)  # 0=未读, 1=已读
    create_time: datetime = Field(default_factory=datetime.now)
