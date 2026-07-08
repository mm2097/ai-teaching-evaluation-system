"""知识模块与知识点模型。对应设计文档 4.2.4、4.2.5 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class KnowledgeModule(SQLModel, table=True):
    """知识模块表 knowledge_module。"""

    __tablename__ = "knowledge_module"

    module_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    module_name: str = Field(max_length=64)
    description: Optional[str] = Field(default=None, max_length=255)
    sort_num: int = Field(default=0)
    create_time: datetime = Field(default_factory=datetime.now)


class KnowledgePoint(SQLModel, table=True):
    """知识点表 knowledge_point。"""

    __tablename__ = "knowledge_point"

    point_id: Optional[int] = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="knowledge_module.module_id", index=True)
    point_name: str = Field(max_length=64)
    description: Optional[str] = Field(default=None, max_length=255)
    sort_num: int = Field(default=0)
    create_time: datetime = Field(default_factory=datetime.now)
