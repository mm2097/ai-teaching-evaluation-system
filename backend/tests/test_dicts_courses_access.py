"""字典/课程接口的鉴权回归测试。

背景：dicts.py 与 courses.py 的全部读接口此前完全无鉴权，未登录即可
枚举班级、学号+姓名名单、教师名录、课程名录（攻击链侦察跳板）；
courses 写接口任何登录用户（含学生）都可建/改/删课程。修复后：

- 全路由要求登录（未登录 401）
- 班级学生名单（学号+姓名）仅教师/管理员
- 课程新增/更新/删除仅管理员
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401 注册全部模型
from app.api.v1.auth import create_token
from app.api.v1.courses import router as courses_router
from app.api.v1.dicts import router as dicts_router
from app.core.database import get_session
from app.models import ClassInfo, Course, CourseStudent, Student, SysRole, SysUser

_TEST_COURSE_CODE = "ACCT209"


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
        s.add(SysRole(role_id=3, role_name="管理员", role_code="admin"))
        s.add(SysUser(user_id=1, username="t1", password="x", real_name="王老师", role_id=1, status=1))
        s.add(SysUser(user_id=2, username="s1", password="x", real_name="张三", role_id=2, status=1))
        s.add(SysUser(user_id=3, username="adm", password="x", real_name="管理员", role_id=3, status=1))
        s.add(SysUser(user_id=4, username="s2", password="x", real_name="李四", role_id=2, status=1))
        s.add(SysUser(user_id=5, username="s3", password="x", real_name="王五", role_id=2, status=1))
        s.add(ClassInfo(class_id=1, class_name="计科2401", college="计算机学院",
                        major="计算机科学与技术", grade="2024级"))
        s.add(Course(course_id=1, course_code="CS101", course_name="数据结构",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院",
                     credit=3, status=1))
        s.add(Student(student_id=1, student_no="2024001", real_name="张三",
                      class_id=1, gender=1, user_id=2))
        s.add(Student(student_id=2, student_no="2024002", real_name="李四",
                      class_id=1, gender=1, user_id=4))
        s.add(Student(student_id=3, student_no="2024003", real_name="王五",
                      class_id=1, gender=1, user_id=5))
        s.add(CourseStudent(course_id=1, student_id=1))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(dicts_router, prefix="/api/v1")
    app.include_router(courses_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth(user_id: int, username: str) -> dict[str, str]:
    token = create_token(user_id, username)
    return {"Authorization": f"Bearer {token}"}


ANONYMOUS_PATHS = [
    "/api/v1/classes",
    "/api/v1/classes/1/students",
    "/api/v1/teachers",
    "/api/v1/dictionaries/semesters",
    "/api/v1/courses",
    "/api/v1/courses/1",
]


def test_dicts_and_courses_require_login(client):
    for path in ANONYMOUS_PATHS:
        assert client.get(path).status_code == 401, path


def test_student_can_use_dropdown_dicts_but_not_roster(client):
    headers = _auth(2, "s1")

    # 下拉字典登录后可用
    assert client.get("/api/v1/classes", headers=headers).status_code == 200
    assert client.get("/api/v1/courses", headers=headers).status_code == 200
    assert client.get("/api/v1/courses/1", headers=headers).status_code == 200

    # 班级学生名单（学号+姓名）禁止学生访问
    assert client.get("/api/v1/classes/1/students", headers=headers).status_code == 403

    # 课程写接口禁止学生访问
    resp = client.post(
        "/api/v1/courses",
        params={"course_code": _TEST_COURSE_CODE, "course_name": "x",
                "teacher_id": 1, "semester": "2024-2025-1", "college": "计算机学院"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_teacher_can_read_class_roster(client):
    headers = _auth(1, "t1")

    resp = client.get("/api/v1/classes/1/students", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert {i["student_no"] for i in items} == {"2024001", "2024002", "2024003"}

    # 教师也不能建课
    resp = client.post(
        "/api/v1/courses",
        params={"course_code": _TEST_COURSE_CODE, "course_name": "x",
                "teacher_id": 1, "semester": "2024-2025-1", "college": "计算机学院"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_admin_can_read_roster_and_manage_courses(engine, client):
    headers = _auth(3, "adm")

    assert client.get("/api/v1/classes/1/students", headers=headers).status_code == 200

    created = client.post(
        "/api/v1/courses",
        params={"course_code": _TEST_COURSE_CODE, "course_name": "鉴权测试课程",
                "teacher_id": 1, "semester": "2024-2025-1", "college": "计算机学院"},
        headers=headers,
    )
    assert created.status_code == 201

    # 清理建课数据，保证同文件内重复运行幂等
    with Session(engine) as s:
        course = s.exec(
            select(Course).where(Course.course_code == _TEST_COURSE_CODE)
        ).first()
        if course:
            s.delete(course)
            s.commit()


def test_admin_post_duplicate_rejected(client):
    """重复建课返回 400（课程编号已存在），确认唯一校验在鉴权后仍生效。"""
    headers = _auth(3, "adm")
    resp = client.post(
        "/api/v1/courses",
        params={"course_code": "ACCT999", "course_name": "x",
                "teacher_id": 1, "semester": "2024-2025-1", "college": "计算机学院"},
        headers=headers,
    )
    assert resp.status_code == 201
    dup = client.post(
        "/api/v1/courses",
        params={"course_code": "ACCT999", "course_name": "x",
                "teacher_id": 1, "semester": "2024-2025-1", "college": "计算机学院"},
        headers=headers,
    )
    assert dup.status_code == 400
