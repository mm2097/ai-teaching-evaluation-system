"""pytest 全局配置。

为所有测试提供：
- 内存 SQLite 测试库（每次会话新建）
- 预置种子数据（1 门课、3 学生、3 次考核、知识点体系）
- Session fixture
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

# 确保能 import app.*
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))


@pytest.fixture(scope="session")
def engine():
    """内存数据库引擎（整个测试会话共享）。"""
    # 必须先导入所有模型，SQLModel.metadata 才能知道全部表
    from app import models  # noqa: F401
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(eng)
    _seed_test_data(eng)
    return eng


@pytest.fixture
def session(engine):
    """每个测试函数独立 Session（函数级隔离）。"""
    with Session(engine) as s:
        yield s


def _seed_test_data(eng):
    """灌入测试种子数据。"""
    from app.models import (
        SysUser, SysRole, Teacher, Student, ClassInfo, Course, CourseStudent,
        KnowledgeModule, KnowledgePoint,
        AttendanceRecord, InteractionRecord,
        ExamBatch, ScoreRecord,
        AiQuestion, AnswerTask, StudentAnswerRecord,
        KnowledgeMastery, StudyWarning,
    )

    with Session(eng) as s:
        # 角色 + 用户
        s.add(SysRole(role_id=1, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=2, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="teacher", password="123456", real_name="王老师", role_id=1, status=1))
        s.commit()

        # 教师 + 班级
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王老师", title="教授",
                       user_id=1, college="计算机学院", phone="138", email="t@edu.cn"))
        s.add(ClassInfo(class_id=1, class_name="计科2401", college="计算机学院", major="计算机科学与技术", grade="2024级"))
        s.commit()

        # 课程
        s.add(Course(course_id=1, course_name="数据结构", course_code="CS101",
                       teacher_id=1, semester="2024-2025-1", college="计算机学院",
                       credit=3, status=1))
        s.commit()

        # 3 个学生
        students = [
            Student(student_id=1, student_no="2024001", real_name="张三", class_id=1,
                    gender=1, user_id=2),
            Student(student_id=2, student_no="2024002", real_name="李四", class_id=1,
                    gender=1, user_id=3),
            Student(student_id=3, student_no="2024003", real_name="王五", class_id=1,
                    gender=0, user_id=4),
        ]
        s.add_all(students)
        for sid in [1, 2, 3]:
            s.add(CourseStudent(course_id=1, student_id=sid))
        # 扩展用户
        s.add(SysUser(user_id=2, username="s1", password="123456", real_name="张三", role_id=2, status=1))
        s.add(SysUser(user_id=3, username="s2", password="123456", real_name="李四", role_id=2, status=1))
        s.add(SysUser(user_id=4, username="s3", password="123456", real_name="王五", role_id=2, status=1))
        s.commit()

        # 知识模块 + 知识点
        s.add(KnowledgeModule(module_id=1, course_id=1, module_name="树结构"))
        s.add(KnowledgeModule(module_id=2, course_id=1, module_name="排序"))
        s.commit()
        kps = [
            KnowledgePoint(point_id=1, module_id=1, point_name="二叉树"),
            KnowledgePoint(point_id=2, module_id=1, point_name="红黑树"),
            KnowledgePoint(point_id=3, module_id=2, point_name="快速排序"),
            KnowledgePoint(point_id=4, module_id=2, point_name="归并排序"),
        ]
        s.add_all(kps)
        s.commit()

        # 3 次考核（构造下滑趋势）
        batches = [
            ExamBatch(batch_id=1, course_id=1, batch_name="作业1", batch_type=1,
                       exam_time=datetime(2024, 9, 1), full_score=100, create_by=1),
            ExamBatch(batch_id=2, course_id=1, batch_name="作业2", batch_type=1,
                       exam_time=datetime(2024, 10, 1), full_score=100, create_by=1),
            ExamBatch(batch_id=3, course_id=1, batch_name="期中", batch_type=3,
                       exam_time=datetime(2024, 11, 1), full_score=100, create_by=1),
        ]
        s.add_all(batches)
        s.commit()

        # 成绩（张三下滑：85→75→55；李四稳定：70→72→68；王五上升：60→70→80）
        scores = [
            # 张三
            ScoreRecord(score_id=1, course_id=1, student_id=1, batch_id=1, score=85, is_pass=1, create_by=1),
            ScoreRecord(score_id=2, course_id=1, student_id=1, batch_id=2, score=75, is_pass=1, create_by=1),
            ScoreRecord(score_id=3, course_id=1, student_id=1, batch_id=3, score=55, is_pass=0, create_by=1),
            # 李四
            ScoreRecord(score_id=4, course_id=1, student_id=2, batch_id=1, score=70, is_pass=1, create_by=1),
            ScoreRecord(score_id=5, course_id=1, student_id=2, batch_id=2, score=72, is_pass=1, create_by=1),
            ScoreRecord(score_id=6, course_id=1, student_id=2, batch_id=3, score=68, is_pass=1, create_by=1),
            # 王五
            ScoreRecord(score_id=7, course_id=1, student_id=3, batch_id=1, score=60, is_pass=1, create_by=1),
            ScoreRecord(score_id=8, course_id=1, student_id=3, batch_id=2, score=70, is_pass=1, create_by=1),
            ScoreRecord(score_id=9, course_id=1, student_id=3, batch_id=3, score=80, is_pass=1, create_by=1),
        ]
        s.add_all(scores)
        s.commit()

        # 考勤（张三缺勤多）
        atts = [
            AttendanceRecord(attendance_id=1, course_id=1, student_id=1, attendance_date=date(2024,9,5), status=0, create_by=1),
            AttendanceRecord(attendance_id=2, course_id=1, student_id=1, attendance_date=date(2024,9,12), status=3, create_by=1),
            AttendanceRecord(attendance_id=3, course_id=1, student_id=1, attendance_date=date(2024,9,19), status=3, create_by=1),
            AttendanceRecord(attendance_id=4, course_id=1, student_id=1, attendance_date=date(2024,9,26), status=3, create_by=1),
            AttendanceRecord(attendance_id=5, course_id=1, student_id=2, attendance_date=date(2024,9,5), status=0, create_by=1),
            AttendanceRecord(attendance_id=6, course_id=1, student_id=2, attendance_date=date(2024,9,12), status=0, create_by=1),
            AttendanceRecord(attendance_id=7, course_id=1, student_id=3, attendance_date=date(2024,9,5), status=0, create_by=1),
            AttendanceRecord(attendance_id=8, course_id=1, student_id=3, attendance_date=date(2024,9,12), status=1, create_by=1),
        ]
        s.add_all(atts)
        s.commit()

        # 互动记录
        ints = [
            InteractionRecord(interaction_id=1, course_id=1, student_id=1, interaction_date=date(2024,9,1), type=1, score=80, create_by=1),
            InteractionRecord(interaction_id=2, course_id=1, student_id=1, interaction_date=date(2024,9,8), type=3, score=90, create_by=1),
            InteractionRecord(interaction_id=3, course_id=1, student_id=2, interaction_date=date(2024,9,1), type=1, score=85, create_by=1),
            InteractionRecord(interaction_id=4, course_id=1, student_id=2, interaction_date=date(2024,9,8), type=1, score=90, create_by=1),
            InteractionRecord(interaction_id=5, course_id=1, student_id=2, interaction_date=date(2024,9,15), type=2, score=85, create_by=1),
            InteractionRecord(interaction_id=6, course_id=1, student_id=3, interaction_date=date(2024,9,1), type=1, score=70, create_by=1),
        ]
        s.add_all(ints)
        s.commit()

        # 知识点掌握度
        kms = [
            # 张三：红黑树薄弱
            KnowledgeMastery(mastery_id=1, course_id=1, student_id=1, point_id=1, mastery_score=75, mastery_level=2),
            KnowledgeMastery(mastery_id=2, course_id=1, student_id=1, point_id=2, mastery_score=30, mastery_level=1),
            KnowledgeMastery(mastery_id=3, course_id=1, student_id=1, point_id=3, mastery_score=65, mastery_level=2),
            KnowledgeMastery(mastery_id=4, course_id=1, student_id=1, point_id=4, mastery_score=70, mastery_level=2),
            # 李四：均衡
            KnowledgeMastery(mastery_id=5, course_id=1, student_id=2, point_id=1, mastery_score=80, mastery_level=3),
            KnowledgeMastery(mastery_id=6, course_id=1, student_id=2, point_id=2, mastery_score=75, mastery_level=2),
            KnowledgeMastery(mastery_id=7, course_id=1, student_id=2, point_id=3, mastery_score=82, mastery_level=3),
            KnowledgeMastery(mastery_id=8, course_id=1, student_id=2, point_id=4, mastery_score=78, mastery_level=2),
            # 王五：上升
            KnowledgeMastery(mastery_id=9, course_id=1, student_id=3, point_id=1, mastery_score=85, mastery_level=3),
            KnowledgeMastery(mastery_id=10, course_id=1, student_id=3, point_id=2, mastery_score=50, mastery_level=2),
            KnowledgeMastery(mastery_id=11, course_id=1, student_id=3, point_id=3, mastery_score=72, mastery_level=2),
            KnowledgeMastery(mastery_id=12, course_id=1, student_id=3, point_id=4, mastery_score=68, mastery_level=2),
        ]
        s.add_all(kms)
        s.commit()

        # AI 题目 + 答题记录（给 mastery 工具用）
        s.add(AiQuestion(question_id=1, course_id=1, point_id=2, type=1,
                          content="红黑树的性质不包括以下哪项？",
                          options='["A.每个节点是红色或黑色","B.根节点是黑色","C.叶子节点是红色","D.红色节点的子节点是黑色"]',
                          correct_answer="C", create_by=1))
        s.commit()
        s.add(StudentAnswerRecord(answer_id=1, task_id=0, question_id=1, student_id=1,
                                   user_answer="C", score=10, is_correct=1))
        s.add(StudentAnswerRecord(answer_id=2, task_id=0, question_id=1, student_id=2,
                                   user_answer="A", score=0, is_correct=0))
        s.commit()

        # 预警记录
        s.add(StudyWarning(warning_id=1, course_id=1, student_id=1, warning_type="W1:成绩下滑",
                            warning_level=2, warning_reason="期中较上次下滑20分", handle_status=0))
        s.commit()
