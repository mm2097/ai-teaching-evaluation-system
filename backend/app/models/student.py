"""学生信息模型。对应设计文档 4.2.3 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Student(SQLModel, table=True):
    """学生信息表 student。"""

    __tablename__ = "student"

    student_id: Optional[int] = Field(default=None, primary_key=True)
    student_no: str = Field(max_length=32, unique=True, index=True)
    real_name: str = Field(max_length=32)
    gender: Optional[int] = Field(default=None)  # 0=女, 1=男
    class_id: int = Field(foreign_key="class_info.class_id", index=True)
    user_id: int = Field(foreign_key="sys_user.user_id", unique=True, index=True)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=64)
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
