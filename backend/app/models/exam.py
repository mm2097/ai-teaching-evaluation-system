"""考核批次与成绩记录模型。对应设计文档 4.3.3、4.3.4 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ExamBatch(SQLModel, table=True):
    """考核批次表 exam_batch。

    联合唯一索引: (course_id, batch_name)
    """

    __tablename__ = "exam_batch"

    batch_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    batch_name: str = Field(max_length=64)
    batch_type: int  # 1=平时成绩, 2=实验成绩, 3=期中, 4=期末
    batch_weight: Optional[float] = Field(default=None)  # 权重百分比，如 60 表示 60%
    exam_time: datetime
    full_score: float = Field(default=100)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class ScoreRecord(SQLModel, table=True):
    """成绩记录表 score_record。

    联合唯一索引: (student_id, batch_id)
    设计备注: 若需知识点级别成绩拆解，可扩展 score_record_detail 子表。
    """

    __tablename__ = "score_record"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    batch_id: int = Field(foreign_key="exam_batch.batch_id", index=True)
    score: float
    is_pass: int = Field(default=1)  # 0=不及格, 1=及格
    remark: Optional[str] = Field(default=None, max_length=255)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
