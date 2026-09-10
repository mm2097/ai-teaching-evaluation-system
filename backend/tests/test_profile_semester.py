"""学情画像学期过滤回归测试。

回归背景：学情分析页选择某学期后，考勤得分仍展示同课程两个学期考勤的平均值。
根因：compute_profile 及其批次类子查询未按学期过滤 exam_batch，
而同一课程在不同学期各有一个考勤批次（unique: course+name+semester）时被一起平均。

覆盖：
- _attendance_rate / _batch_scores_by_keyword 按学期过滤
- compute_profile 画像的考勤轴/可用性按学期取数
- /analysis/profile 接口透传 semester 参数
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  确保所有表注册到 metadata
from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import create_token
from app.core.database import get_session
from app.models import (
    AttendanceSheet,
    ClassInfo,
    Course,
    CourseStudent,
    ExamBatch,
    Student,
    SysRole,
    SysUser,
    Teacher,
)
from app.services.profile import _attendance_rate, compute_profile

COURSE_ID = 9501
STUDENT_ID = 9501
SEM_ONE = "2024-2025-1"
SEM_TWO = "2024-2025-2"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(SysRole(role_id=1, role_name="教师", role_code="teacher"))
        s.add(SysUser(user_id=1, username="teacher", password="x", real_name="王老师", role_id=1, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王老师", user_id=1, college="计算机学院"))
        s.add(ClassInfo(class_id=1, class_name="软件1801班", college="计算机学院"))
        s.add(Course(course_id=COURSE_ID, course_code="T9501", course_name="学期过滤课",
                     teacher_id=1, semester=SEM_ONE, college="计算机学院"))
        s.add(Student(student_id=STUDENT_ID, student_no="95001", real_name="测一",
                      class_id=1, user_id=2))
        s.add(CourseStudent(course_id=COURSE_ID, student_id=STUDENT_ID))
        # 同一课程两个学期各一个考勤批次（同批次名，学期不同）
        batch_one = ExamBatch(course_id=COURSE_ID, batch_name="学期过滤课-考勤情况",
                              batch_type=5, semester=SEM_ONE, create_by=1)
        batch_two = ExamBatch(course_id=COURSE_ID, batch_name="学期过滤课-考勤情况",
                              batch_type=5, semester=SEM_TWO, create_by=1)
        s.add(batch_one)
        s.add(batch_two)
        s.commit()
        s.refresh(batch_one)
        s.refresh(batch_two)
        s.add(AttendanceSheet(student_id=STUDENT_ID, exam_batch_id=batch_one.batch_id,
                              attendance_rate=0.8, create_by=1))
        s.add(AttendanceSheet(student_id=STUDENT_ID, exam_batch_id=batch_two.batch_id,
                              attendance_rate=0.4, create_by=1))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(analysis_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _teacher_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'teacher')}"}


def test_attendance_rate_without_semester_averages_all(engine):
    """不传学期时保持旧行为：两个学期考勤平均（0.8+0.4)/2=0.6。"""
    with Session(engine) as s:
        assert _attendance_rate(s, STUDENT_ID, COURSE_ID) == pytest.approx(0.6)


def test_attendance_rate_filtered_by_semester(engine):
    """传学期时仅取该学期考勤批次，不再跨学期平均。"""
    with Session(engine) as s:
        assert _attendance_rate(s, STUDENT_ID, COURSE_ID, semester=SEM_ONE) == pytest.approx(0.8)
        assert _attendance_rate(s, STUDENT_ID, COURSE_ID, semester=SEM_TWO) == pytest.approx(0.4)


def test_compute_profile_attendance_scoped_by_semester(engine):
    """画像考勤子项与可用性按学期取数。"""
    with Session(engine) as s:
        one = compute_profile(s, STUDENT_ID, COURSE_ID, semester=SEM_ONE)
        assert one.attendance_rate == pytest.approx(0.8)
        assert one.attendance_score == pytest.approx(80.0)
        assert one.attendance_available is True

        two = compute_profile(s, STUDENT_ID, COURSE_ID, semester=SEM_TWO)
        assert two.attendance_rate == pytest.approx(0.4)
        assert two.attendance_available is True

        # 该学期无考勤数据 → 0 分且标记无数据
        none = compute_profile(s, STUDENT_ID, COURSE_ID, semester="2023-2024-1")
        assert none.attendance_rate == 0.0
        assert none.attendance_available is False


def test_profile_api_passes_semester(client):
    """/analysis/profile 接口按 semester 参数过滤考勤轴。"""
    resp_all = client.get(
        "/api/v1/analysis/profile",
        params={"student_id": STUDENT_ID, "course_id": COURSE_ID},
        headers=_teacher_auth(),
    )
    assert resp_all.status_code == 200
    assert resp_all.json()["radarValues"][1] == pytest.approx(60.0)

    resp_one = client.get(
        "/api/v1/analysis/profile",
        params={"student_id": STUDENT_ID, "course_id": COURSE_ID, "semester": SEM_ONE},
        headers=_teacher_auth(),
    )
    assert resp_one.status_code == 200
    assert resp_one.json()["radarValues"][1] == pytest.approx(80.0)

    resp_two = client.get(
        "/api/v1/analysis/profile",
        params={"student_id": STUDENT_ID, "course_id": COURSE_ID, "semester": SEM_TWO},
        headers=_teacher_auth(),
    )
    assert resp_two.status_code == 200
    assert resp_two.json()["radarValues"][1] == pytest.approx(40.0)
