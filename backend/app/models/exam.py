"""考核批次与成绩记录模型。对应设计文档 4.3.3、4.3.4 节。

注意：ScoreRecord 已被三张专用成绩表替代（见 score_tables.py），保留此模型
仅为兼容旧数据查询。新导入数据请使用 IndividualScore / CourseTestDetail。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class ExamBatch(SQLModel, table=True):
    """考核批次表 exam_batch。

    联合唯一索引: (course_id, batch_name, semester)
    相同测试名称 + 相同学期 = 同一批次。
    batch_type: 1=平时成绩, 2=实验成绩, 3=期中, 4=期末, 5=考勤
    """

    __tablename__ = "exam_batch"
    __table_args__ = (
        UniqueConstraint("course_id", "batch_name", "semester",
                         name="uq_exam_batch_course_name_semester"),
    )

    batch_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    batch_name: str = Field(max_length=64)
    batch_type: int  # 1=平时成绩, 2=实验成绩, 3=期中, 4=期末, 5=考勤
    semester: str = Field(default="", max_length=32)  # 学期，如 2025-2026-1
    batch_weight: Optional[float] = Field(default=None)  # 权重百分比，如 60 表示 60%
    full_score: float = Field(default=100)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class ScoreRecord(SQLModel, table=True):
    """成绩记录表 score_record（已废弃，保留兼容旧数据）。

    新数据请使用：
      - IndividualScore  → 单项成绩
      - CourseTestDetail → 课程测试各题扣分情况
      - AttendanceSheet  → 考勤情况

    联合唯一索引: (student_id, batch_id)
    """

    __tablename__ = "score_record"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    batch_id: int = Field(foreign_key="exam_batch.batch_id", index=True)
    score: float
    is_pass: int = Field(default=1)  # 0=不及格, 1=及格
    remark: Optional[str] = Field(default=None, max_length=255)
    source_data: Optional[str] = Field(default=None)  # 原始上传行数据 JSON
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
