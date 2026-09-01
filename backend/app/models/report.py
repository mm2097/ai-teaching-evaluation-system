"""Persisted report snapshots."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class ReportHistory(SQLModel, table=True):
    """Immutable snapshot created when a user generates a report."""

    __tablename__ = "report_history"

    report_id: Optional[int] = Field(default=None, primary_key=True)
    creator_user_id: int = Field(foreign_key="sys_user.user_id", index=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    report_type: int = Field(index=True)
    scope: str = Field(max_length=16)
    class_id: Optional[int] = Field(default=None, foreign_key="class_info.class_id")
    student_id: Optional[int] = Field(default=None, foreign_key="student.student_id")
    export_format: str = Field(default="pdf", max_length=8)
    report_name: str = Field(max_length=255)
    course_name: str = Field(max_length=64)
    class_name: Optional[str] = Field(default=None, max_length=64)
    student_name: Optional[str] = Field(default=None, max_length=32)
    parameter_snapshot: str = Field(sa_column=Column(Text, nullable=False))
    report_snapshot: str = Field(sa_column=Column(Text, nullable=False))
    stats_snapshot: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.now, index=True)
