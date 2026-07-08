"""教师信息模型。对应设计文档 4.2.1 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Teacher(SQLModel, table=True):
    """教师信息表 teacher。"""

    __tablename__ = "teacher"

    teacher_id: Optional[int] = Field(default=None, primary_key=True)
    teacher_no: str = Field(max_length=32, unique=True, index=True)
    real_name: str = Field(max_length=32)
    title: Optional[str] = Field(default=None, max_length=32)
    user_id: int = Field(foreign_key="sys_user.user_id", unique=True, index=True)
    college: str = Field(max_length=64)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=64)
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
