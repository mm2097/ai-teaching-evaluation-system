"""三张专用成绩表，分别对应三种数据模板。

替代通用 ScoreRecord 的设计：
  - individual_score     → 单项成绩模板
  - attendance_sheet     → 考勤情况模板（32次课考勤槽位）
  - course_test_detail   → 课程测试各题扣分情况模板

设计原则：有了 student_id 就不存学号；有了 exam_batch_id 就不存课程/学期/名称。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Text
from sqlmodel import Field, SQLModel


class IndividualScore(SQLModel, table=True):
    """单项成绩表 individual_score。

    对应模板「单项成绩」：每行一条成绩记录，按成绩名称区分不同考试/考查项目。
    同一学生 + 同一 exam_batch 唯一。
    """

    __tablename__ = "individual_score"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    exam_batch_id: int = Field(foreign_key="exam_batch.batch_id", index=True)
    score: float
    source_data: Optional[str] = Field(default=None, sa_type=Text)  # 原始上传行数据 JSON
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class AttendanceSheet(SQLModel, table=True):
    """考勤情况表 attendance_sheet。

    对应模板「成绩考勤情况」：每位学生一行，包含 32 次课的考勤状态。
    设计成列式存储（attendance_1 ~ attendance_32），与模板结构一一对应。
    """

    __tablename__ = "attendance_sheet"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    exam_batch_id: int = Field(foreign_key="exam_batch.batch_id", index=True)

    # 32 次考勤槽位（值：到 / 缺 / 请假 / 迟到 / 早退）
    attendance_1: Optional[str] = Field(default=None, max_length=8)
    attendance_2: Optional[str] = Field(default=None, max_length=8)
    attendance_3: Optional[str] = Field(default=None, max_length=8)
    attendance_4: Optional[str] = Field(default=None, max_length=8)
    attendance_5: Optional[str] = Field(default=None, max_length=8)
    attendance_6: Optional[str] = Field(default=None, max_length=8)
    attendance_7: Optional[str] = Field(default=None, max_length=8)
    attendance_8: Optional[str] = Field(default=None, max_length=8)
    attendance_9: Optional[str] = Field(default=None, max_length=8)
    attendance_10: Optional[str] = Field(default=None, max_length=8)
    attendance_11: Optional[str] = Field(default=None, max_length=8)
    attendance_12: Optional[str] = Field(default=None, max_length=8)
    attendance_13: Optional[str] = Field(default=None, max_length=8)
    attendance_14: Optional[str] = Field(default=None, max_length=8)
    attendance_15: Optional[str] = Field(default=None, max_length=8)
    attendance_16: Optional[str] = Field(default=None, max_length=8)
    attendance_17: Optional[str] = Field(default=None, max_length=8)
    attendance_18: Optional[str] = Field(default=None, max_length=8)
    attendance_19: Optional[str] = Field(default=None, max_length=8)
    attendance_20: Optional[str] = Field(default=None, max_length=8)
    attendance_21: Optional[str] = Field(default=None, max_length=8)
    attendance_22: Optional[str] = Field(default=None, max_length=8)
    attendance_23: Optional[str] = Field(default=None, max_length=8)
    attendance_24: Optional[str] = Field(default=None, max_length=8)
    attendance_25: Optional[str] = Field(default=None, max_length=8)
    attendance_26: Optional[str] = Field(default=None, max_length=8)
    attendance_27: Optional[str] = Field(default=None, max_length=8)
    attendance_28: Optional[str] = Field(default=None, max_length=8)
    attendance_29: Optional[str] = Field(default=None, max_length=8)
    attendance_30: Optional[str] = Field(default=None, max_length=8)
    attendance_31: Optional[str] = Field(default=None, max_length=8)
    attendance_32: Optional[str] = Field(default=None, max_length=8)

    # 汇总列
    total_count: Optional[int] = Field(default=None)       # 考勤总数
    present_count: Optional[int] = Field(default=None)      # 到课数
    leave_count: Optional[int] = Field(default=None)        # 请假数
    late_count: Optional[int] = Field(default=None)         # 迟到数
    early_leave_count: Optional[int] = Field(default=None)  # 早退数
    attendance_rate: Optional[float] = Field(default=None)  # 到课率

    source_data: Optional[str] = Field(default=None, sa_type=Text)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)


class CourseTestDetail(SQLModel, table=True):
    """课程测试各题扣分情况表 course_test_detail。

    对应模板「课程测试各题扣分情况」：每位学生一行，包含 5 道大题的扣分和知识点。
    """

    __tablename__ = "course_test_detail"

    score_id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    exam_batch_id: int = Field(foreign_key="exam_batch.batch_id", index=True)

    # 各题扣分
    question1_score: Optional[float] = Field(default=None)
    question2_score: Optional[float] = Field(default=None)
    question3_score: Optional[float] = Field(default=None)
    question4_score: Optional[float] = Field(default=None)
    question5_score: Optional[float] = Field(default=None)

    # 各题扣分知识点
    question1_knowledge: Optional[str] = Field(default=None, max_length=64)
    question2_knowledge: Optional[str] = Field(default=None, max_length=64)
    question3_knowledge: Optional[str] = Field(default=None, max_length=64)
    question4_knowledge: Optional[str] = Field(default=None, max_length=64)
    question5_knowledge: Optional[str] = Field(default=None, max_length=64)

    # 总成绩（实际得分，满分 100）
    total_score: float

    source_data: Optional[str] = Field(default=None, sa_type=Text)
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)
