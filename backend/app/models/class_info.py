"""班级信息模型。对应设计文档 4.2.2 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ClassInfo(SQLModel, table=True):
    """班级信息表 class_info。"""

    __tablename__ = "class_info"

    class_id: Optional[int] = Field(default=None, primary_key=True)
    class_name: str = Field(max_length=64)
    college: str = Field(max_length=64)
    enroll_year: int
    create_time: datetime = Field(default_factory=datetime.now)
