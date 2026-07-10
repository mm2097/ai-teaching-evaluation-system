"""AI 题目、答题任务、答题记录模型。对应设计文档 4.4.1~4.4.4 节。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Text
from sqlmodel import Field, SQLModel


class AiQuestion(SQLModel, table=True):
    """AI 题目表 ai_question。"""

    __tablename__ = "ai_question"

    question_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    point_id: int = Field(foreign_key="knowledge_point.point_id", index=True)
    type: int  # 1=单选, 2=多选, 3=判断, 4=填空, 5=简答
    content: str = Field(sa_type=Text)
    options: Optional[str] = Field(default=None, sa_type=Text)  # JSON 格式
    correct_answer: str = Field(sa_type=Text)
    analysis: Optional[str] = Field(default=None, sa_type=Text)
    difficulty: str = Field(default="medium", max_length=10)  # easy/medium/hard
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)


class AnswerTask(SQLModel, table=True):
    """答题任务表 answer_task。"""

    __tablename__ = "answer_task"

    task_id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.course_id", index=True)
    task_name: str = Field(max_length=64)
    publish_time: datetime = Field(default_factory=datetime.now)
    deadline: datetime
    status: int = Field(default=0)  # 0=未开始, 1=进行中, 2=已结束
    create_by: int = Field(foreign_key="sys_user.user_id")
    create_time: datetime = Field(default_factory=datetime.now)


class TaskQuestion(SQLModel, table=True):
    """答题任务-题目关联表 task_question。"""

    __tablename__ = "task_question"

    rel_id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="answer_task.task_id", index=True)
    question_id: int = Field(foreign_key="ai_question.question_id", index=True)
    sort_num: int = Field(default=0)
    create_time: datetime = Field(default_factory=datetime.now)


class StudentAnswerRecord(SQLModel, table=True):
    """学生答题记录表 student_answer_record。"""

    __tablename__ = "student_answer_record"

    answer_id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="answer_task.task_id", index=True)
    question_id: int = Field(foreign_key="ai_question.question_id", index=True)
    student_id: int = Field(foreign_key="student.student_id", index=True)
    user_answer: Optional[str] = Field(default=None, sa_type=Text)
    score: float = Field(default=0)
    is_correct: int = Field(default=0)  # 0=错误, 1=正确
    ai_score: Optional[float] = Field(default=None)  # AI 建议分（老师可终判覆盖）
    judge_reason: Optional[str] = Field(default=None, sa_type=Text)  # AI 判分依据
    answer_time: datetime = Field(default_factory=datetime.now)
    submit_time: datetime = Field(default_factory=datetime.now)
