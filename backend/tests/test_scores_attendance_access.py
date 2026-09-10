"""成绩/考勤接口的学生越权（IDOR）回归测试。

背景：score-records / attendance-records 路由的 require_teaching_user
包含学生角色，但端点内无归属校验，任一学生传任意 student_id 即可读取
全校任意学生的成绩与考勤。修复后：学生强制收敛为本人数据。

- GET /score-records：学生自动只返回本人（无参或带本人 id），传他人 id 403
- GET /score-records/student/{id}：学生仅可查本人
- GET /attendance-records：同上
- 教师/管理员不受限；未绑定学生档案的学生账号 403
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401 注册全部模型
from app.api.v1.auth import create_token
from app.api.v1.attendance import router as attendance_router
from app.api.v1.scores import router as scores_router
from app.core.database import get_session
from app.models import (
    AttendanceRecord, ClassInfo, Course, ExamBatch, ScoreRecord,
    Student, SysRole, SysUser,
)


@pytest.fixture(scope="module")
def engine():
    """独立内存库（StaticPool 保证所有线程共用同一连接）。"""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(SysRole(role_id=1, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=2, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="t1", password="x", real_name="王老师", role_id=1, status=1))
        s.add(SysUser(user_id=2, username="s1", password="x", real_name="张三", role_id=2, status=1))
        s.add(SysUser(user_id=3, username="s-noprofile", password="x", real_name="无档案学生", role_id=2, status=1))
        s.add(SysUser(user_id=4, username="s2", password="x", real_name="李四", role_id=2, status=1))
        s.add(ClassInfo(class_id=1, class_name="计科2401", college="计算机学院",
                        major="计算机科学与技术", grade="2024级"))
        s.add(Course(course_id=1, course_code="CS101", course_name="数据结构",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院",
                     credit=3, status=1))
        s.add(ExamBatch(batch_id=1, course_id=1, batch_name="作业1", batch_type=1,
                        exam_time=datetime(2024, 9, 1), full_score=100, create_by=1))
        s.add(Student(student_id=1, student_no="2024001", real_name="张三",
                      class_id=1, gender=1, user_id=2))
        s.add(Student(student_id=2, student_no="2024002", real_name="李四",
                      class_id=1, gender=1, user_id=4))
        s.add(ScoreRecord(score_id=1, course_id=1, student_id=1, batch_id=1,
                          score=85, is_pass=1, create_by=1))
        s.add(ScoreRecord(score_id=2, course_id=1, student_id=2, batch_id=1,
                          score=70, is_pass=1, create_by=1))
        s.add(AttendanceRecord(attendance_id=1, course_id=1, student_id=1,
                               attendance_date=date(2024, 9, 5), status=0, create_by=1))
        s.add(AttendanceRecord(attendance_id=2, course_id=1, student_id=2,
                               attendance_date=date(2024, 9, 5), status=3, create_by=1))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(scores_router, prefix="/api/v1")
    app.include_router(attendance_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth(user_id: int, username: str) -> dict[str, str]:
    token = create_token(user_id, username)
    return {"Authorization": f"Bearer {token}"}


def _student_headers() -> dict[str, str]:
    return _auth(2, "s1")


def test_student_sees_only_own_scores(client):
    headers = _student_headers()

    # 无参：自动收敛为本人
    items = client.get("/api/v1/score-records", headers=headers).json()
    assert len(items) == 1
    assert items[0]["student_id"] == 1
    assert items[0]["score"] == 85

    # 显式传本人 id：同样只看到本人
    items = client.get(
        "/api/v1/score-records", params={"student_id": 1}, headers=headers
    ).json()
    assert [i["student_id"] for i in items] == [1]


def test_student_cannot_read_other_scores(client):
    headers = _student_headers()

    assert client.get(
        "/api/v1/score-records", params={"student_id": 2}, headers=headers
    ).status_code == 403
    assert client.get(
        "/api/v1/score-records/student/2", headers=headers
    ).status_code == 403


def test_student_detail_own_allowed(client):
    headers = _student_headers()

    resp = client.get("/api/v1/score-records/student/1", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_id"] == 1
    assert body["courses"][0]["details"][0]["score"] == 85


def test_student_attendance_scoped(client):
    headers = _student_headers()

    items = client.get("/api/v1/attendance-records", headers=headers).json()
    assert [i["student_id"] for i in items] == [1]
    assert items[0]["status"] == "出勤"

    assert client.get(
        "/api/v1/attendance-records", params={"student_id": 2}, headers=headers
    ).status_code == 403


def test_teacher_unrestricted(client):
    headers = _auth(1, "t1")

    items = client.get("/api/v1/score-records", headers=headers).json()
    assert {i["student_id"] for i in items} == {1, 2}

    resp = client.get("/api/v1/score-records/student/2", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["student_id"] == 2

    items = client.get("/api/v1/attendance-records", headers=headers).json()
    assert {i["student_id"] for i in items} == {1, 2}


def test_student_without_profile_rejected(client):
    headers = _auth(3, "s-noprofile")

    assert client.get("/api/v1/score-records", headers=headers).status_code == 403
    assert client.get("/api/v1/score-records/student/1", headers=headers).status_code == 403
    assert client.get("/api/v1/attendance-records", headers=headers).status_code == 403
