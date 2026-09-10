"""分析结果模型。对应设计文档 4.6.1~4.6.3 节。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
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


class CTAchievement(SQLModel, table=True):
    """课程目标达成度记录表 ct_achievement。

    联合唯一索引: (course_id, student_id)
    每次 refresh_course_analysis 时重算覆盖。
    8 个 CT 达成度采用列式存储（CT 固定不变，便于 SQL 聚合与前端取值）。
    """

    __tablename__ = "ct_achievement"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_ct_course_student"),
    )

    achievement_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)

    # 8 个 CT 达成度（0-100，None 表示无证据）
    ct1_score: Optional[float] = Field(default=None)
    ct2_score: Optional[float] = Field(default=None)
    ct3_score: Optional[float] = Field(default=None)
    ct4_score: Optional[float] = Field(default=None)
    ct5_score: Optional[float] = Field(default=None)
    ct6_score: Optional[float] = Field(default=None)
    ct7_score: Optional[float] = Field(default=None)
    ct8_score: Optional[float] = Field(default=None)

    # 各 CT 置信度（high/medium/low），逗号分隔，顺序同 CT1-8
    ct_confidence: Optional[str] = Field(default=None, max_length=64)

    overall_score: float          # 总体达成度（有证据 CT 的均值）
    overall_level: str            # 总体达成等级
    weak_cts: Optional[str] = Field(default=None, max_length=64)   # 达成度<60 的 CT 编号
    strong_cts: Optional[str] = Field(default=None, max_length=64) # 达成度≥85 的 CT 编号
    update_time: datetime = Field(default_factory=datetime.now)
