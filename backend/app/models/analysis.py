"""分析结果模型。对应设计文档 4.6.1~4.6.3 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class KnowledgeMastery(SQLModel, table=True):
    """知识点掌握度记录表 knowledge_mastery。

    联合唯一索引: (course_id, student_id, point_id)
    """

    __tablename__ = "knowledge_mastery"

    mastery_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    point_id: int = Field(foreign_key="knowledge_point.point_id", index=True)
    mastery_score: float  # 0~100
    mastery_level: int  # 1=未掌握, 2=基本掌握, 3=熟练掌握
    update_time: datetime = Field(default_factory=datetime.now)


class StudyWarning(SQLModel, table=True):
    """学情预警记录表 study_warning。"""

    __tablename__ = "study_warning"

    warning_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    warning_type: str = Field(max_length=32)  # 成绩下滑、缺勤超标、作业未交
    warning_level: int  # 1=低, 2=中, 3=高
    warning_reason: str = Field(max_length=255)
    handle_status: int = Field(default=0)  # 0=未处理, 1=已处理
    create_time: datetime = Field(default_factory=datetime.now)


class StudentProfile(SQLModel, table=True):
    """学情画像结果表 student_profile。

    联合唯一索引: (course_id, student_id)
    """

    __tablename__ = "student_profile"

    profile_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    academic_score: float  # 学业水平维度得分
    attitude_score: float  # 学习态度维度得分
    progress_score: float  # 学习进步维度得分
    total_profile_score: float  # 画像综合得分
    study_tags: Optional[str] = Field(default=None, max_length=255)  # 逗号分隔
    good_modules: Optional[str] = Field(default=None, max_length=255)
    weak_modules: Optional[str] = Field(default=None, max_length=255)
    update_time: datetime = Field(default_factory=datetime.now)
