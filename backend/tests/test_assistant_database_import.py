"""助教角色与 SQLite 教学数据导入回归测试。"""
import sqlite3

import pytest
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1 import assistants, auth, courses, teaching_data
from app.core.security import hash_password
from app.models import (
    Course, CourseAssistant, IndividualScore, Student, SysRole, SysUser,
    Teacher, TeachingAssistant,
)
from app.services.file_import import import_file


@pytest.fixture
def assistant_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            SysRole(role_id=1, role_name="管理员", role_code="admin"),
            SysRole(role_id=2, role_name="教师", role_code="teacher"),
            SysRole(role_id=3, role_name="学生", role_code="student"),
            SysRole(role_id=4, role_name="课程助教", role_code="assistant"),
            SysUser(user_id=1, username="teacher", password=hash_password("123456"),
                    real_name="王老师", role_id=2, status=1),
            SysUser(user_id=2, username="assistant", password=hash_password("123456"),
                    real_name="周助教", role_id=4, status=1, college="计算机学院"),
            SysUser(user_id=3, username="student", password=hash_password("123456"),
                    real_name="张三", role_id=3, status=1),
            Teacher(teacher_id=1, teacher_no="T001", real_name="王老师",
                    user_id=1, college="计算机学院"),
            TeachingAssistant(assistant_id=1, assistant_no="A001", real_name="周助教",
                              user_id=2, college="计算机学院"),
            Course(course_id=1, course_code="CS101", course_name="数据结构",
                   teacher_id=1, semester="2025-2026-1", college="计算机学院"),
            Course(course_id=2, course_code="CS102", course_name="操作系统",
                   teacher_id=1, semester="2025-2026-1", college="计算机学院"),
            CourseAssistant(course_id=1, assistant_id=1),
            Student(student_id=1, student_no="2024001", real_name="张三", class_id=1, user_id=3),
        ])
        session.commit()
    return engine


def test_assistant_dedicated_login_and_assigned_courses(assistant_engine):
    with Session(assistant_engine) as session:
        response = auth.assistant_login(
            auth.LoginRequest(username="assistant", password="123456"), session
        )
        assert response.user.role_code == "assistant"
        assert response.user.assistant_no == "A001"

        user = session.get(SysUser, 2)
        my_courses = courses.list_my_courses(session, user)
        assert [course["course_id"] for course in my_courses] == [1]


def test_assistant_login_rejects_other_roles(assistant_engine):
    with Session(assistant_engine) as session:
        with pytest.raises(HTTPException) as exc_info:
            auth.assistant_login(
                auth.LoginRequest(username="teacher", password="123456"), session
            )
        assert exc_info.value.status_code == 403


def test_assistant_course_scope_is_enforced(assistant_engine):
    with Session(assistant_engine) as session:
        user = session.get(SysUser, 2)
        assert teaching_data._require_teacher_for_course(user, 1, session).assistant_id == 1
        with pytest.raises(HTTPException) as exc_info:
            teaching_data._require_teacher_for_course(user, 2, session)
        assert exc_info.value.status_code == 403


def test_sqlite_database_import_writes_business_tables(assistant_engine, tmp_path):
    database_path = tmp_path / "teaching-data.db"
    connection = sqlite3.connect(database_path)
    connection.execute(
        'CREATE TABLE "单项成绩" ('
        '"学号" TEXT, "姓名" TEXT, "学期" TEXT, "成绩名称" TEXT, "成绩" REAL)'
    )
    connection.execute(
        'INSERT INTO "单项成绩" VALUES (?, ?, ?, ?, ?)',
        ("2024001", "张三", "2025-2026-1", "作业1", 88),
    )
    connection.commit()
    connection.close()

    with Session(assistant_engine) as session:
        result = import_file(
            session, str(database_path), ".db", course_id=1,
            create_by=2, file_name="teaching-data.db",
        )
        assert result.error_count == 0
        assert result.success_count == 1
        score = session.exec(select(IndividualScore)).first()
        assert score is not None
        assert score.score == 88
