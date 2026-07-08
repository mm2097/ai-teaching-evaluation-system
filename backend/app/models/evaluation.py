"""评价管理模型。对应设计文档 4.5.1~4.5.4 节。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Text
from sqlmodel import Field, SQLModel


class EvalDimension(SQLModel, table=True):
    """评价维度表 eval_dimension。"""

    __tablename__ = "eval_dimension"

    dimension_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: Optional[int] = Field(default=None, foreign_key="course.course_id", index=True)
    dimension_name: str = Field(max_length=32)
    description: Optional[str] = Field(default=None, max_length=255)
    sort_num: int = Field(default=0)
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class EvalIndex(SQLModel, table=True):
    """评价指标表 eval_index。"""

    __tablename__ = "eval_index"

    index_id: Optional[int] = Field(default=None, primary_key=True)
    dimension_id: int = Field(foreign_key="eval_dimension.dimension_id", index=True)
    index_name: str = Field(max_length=64)
    weight: float  # 权重百分比，如 20 表示 20%
    score_rule: str = Field(sa_type=Text)  # JSON 格式
    description: Optional[str] = Field(default=None, max_length=255)
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class StudentEvaluationResult(SQLModel, table=True):
    """学生学习评价结果表 student_evaluation_result。"""

    __tablename__ = "student_evaluation_result"

    eval_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    total_score: float
    eval_level: str = Field(max_length=16)  # 优秀、良好、中等、及格、不及格
    eval_time: datetime = Field(default_factory=datetime.now)
    create_time: datetime = Field(default_factory=datetime.now)


class EvalDimensionScore(SQLModel, table=True):
    """评价维度得分表 eval_dimension_score。"""

    __tablename__ = "eval_dimension_score"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    eval_id: int = Field(foreign_key="student_evaluation_result.eval_id", index=True)
    dimension_id: int = Field(foreign_key="eval_dimension.dimension_id", index=True)
    dimension_score: float
    create_time: datetime = Field(default_factory=datetime.now)
