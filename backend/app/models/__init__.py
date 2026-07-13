"""数据模型存放处。

新增模型步骤:
1. 在本目录下新建文件(如 user.py),定义 table=True 的 SQLModel
2. 在本文件里加上对应的 import
3. 重启后端,init_db() 会自动建表
"""

from app.models.user import SysUser, SysRole, LoginRequest, UserCreate, UserRead, UserUpdate
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.class_info import ClassInfo
from app.models.course import Course, CourseStudent
from app.models.knowledge import KnowledgeModule, KnowledgePoint
from app.models.attendance import AttendanceRecord
from app.models.interaction import InteractionRecord
from app.models.exam import ExamBatch, ScoreRecord
from app.models.question import AiQuestion, AnswerTask, AnswerTaskClass, TaskQuestion, StudentAnswerRecord
from app.models.evaluation import EvalDimension, EvalIndex, StudentEvaluationResult, EvalDimensionScore
from app.models.analysis import KnowledgeMastery, StudyWarning, StudentProfile
from app.models.log import SysOperationLog

__all__ = [
    "SysUser", "SysRole", "LoginRequest", "UserCreate", "UserRead", "UserUpdate",
    "Teacher", "Student", "ClassInfo",
    "Course", "CourseStudent",
    "KnowledgeModule", "KnowledgePoint",
    "AttendanceRecord", "InteractionRecord",
    "ExamBatch", "ScoreRecord",
    "AiQuestion", "AnswerTask", "AnswerTaskClass", "TaskQuestion", "StudentAnswerRecord",
    "EvalDimension", "EvalIndex", "StudentEvaluationResult", "EvalDimensionScore",
    "KnowledgeMastery", "StudyWarning", "StudentProfile",
    "SysOperationLog",
]
