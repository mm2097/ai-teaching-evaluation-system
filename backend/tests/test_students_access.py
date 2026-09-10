"""学生管理接口的鉴权与脱敏回归测试。

背景：GET /students 与 GET /students/{id} 此前完全无鉴权，未登录即可
枚举全班姓名/学号/手机号/邮箱。修复后：

- 全路由要求登录（未登录 401）
- 学生（及其它非教学角色）仅能返回/查看本人档案
- 教师可见名单但联系方式脱敏；管理员可见完整联系方式
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import pytest

from app import models  # noqa: F401 注册全部模型
from app.api.v1.auth import create_token
from app.api.v1.students import router as students_router
from app.core.database import get_session
from app.models import ClassInfo, Student, SysRole, SysUser

_TEST_STUDENT_ID = 208
_TEST_USER_ID = 208
_TEST_PHONE = "13812345678"
_TEST_EMAIL = "zhang@example.com"


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
        s.add(SysUser(user_id=_TEST_USER_ID, username="contact-stu", password="x",
                      real_name="联系方式测试生", role_id=2, status=1))
        s.add(SysUser(user_id=4, username="s2", password="x", real_name="李四", role_id=2, status=1))
        s.add(SysUser(user_id=5, username="s-noprofile", password="x",
                      real_name="无档案学生", role_id=2, status=1))
        s.add(ClassInfo(class_id=1, class_name="计科2401", college="计算机学院",
                        major="计算机科学与技术", grade="2024级"))
        s.add(Student(student_id=1, student_no="2024001", real_name="张三",
                      class_id=1, gender=1, user_id=2))
        s.add(Student(student_id=2, student_no="2024002", real_name="李四",
                      class_id=1, gender=1, user_id=4))
        s.add(Student(student_id=_TEST_STUDENT_ID, student_no="2024208",
                      real_name="联系方式测试生", class_id=1, gender=1,
                      user_id=_TEST_USER_ID, phone=_TEST_PHONE, email=_TEST_EMAIL))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(students_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth(user_id: int, username: str) -> dict[str, str]:
    token = create_token(user_id, username)
    return {"Authorization": f"Bearer {token}"}


def _teacher_headers() -> dict[str, str]:
    return _auth(1, "t1")


def _student_headers() -> dict[str, str]:
    return _auth(2, "s1")


def _admin_headers() -> dict[str, str]:
    return _auth(3, "adm")


def test_students_requires_login(client):
    assert client.get("/api/v1/students").status_code == 401
    assert client.get("/api/v1/students/1").status_code == 401


def test_student_role_sees_only_self(client):
    headers = _student_headers()

    items = client.get("/api/v1/students", headers=headers).json()
    assert [item["student_id"] for item in items] == [1]

    # 传筛选条件也只返回本人
    items = client.get(
        "/api/v1/students", params={"class_id": 1, "keyword": "李四"}, headers=headers
    ).json()
    assert [item["student_id"] for item in items] == [1]

    # 他人档案 403，本人档案 200
    assert client.get("/api/v1/students/2", headers=headers).status_code == 403
    own = client.get("/api/v1/students/1", headers=headers)
    assert own.status_code == 200
    assert own.json()["student_no"] == "2024001"


def test_teacher_sees_roster_with_masked_contact(client):
    headers = _teacher_headers()

    detail = client.get(f"/api/v1/students/{_TEST_STUDENT_ID}", headers=headers).json()
    assert detail["phone"] == "138****5678"
    assert detail["email"] == "z***@example.com"

    items = client.get("/api/v1/students", headers=headers).json()
    target = next(i for i in items if i["student_id"] == _TEST_STUDENT_ID)
    assert target["phone"] == "138****5678"
    assert target["email"] == "z***@example.com"


def test_admin_sees_full_contact(client):
    detail = client.get(f"/api/v1/students/{_TEST_STUDENT_ID}", headers=_admin_headers()).json()
    assert detail["phone"] == _TEST_PHONE
    assert detail["email"] == _TEST_EMAIL


def test_student_role_without_profile_sees_nothing(client):
    """学生角色但未绑定档案 → 空列表/403（失败关闭）。"""
    headers = _auth(5, "s-noprofile")

    assert client.get("/api/v1/students", headers=headers).json() == []
    assert client.get("/api/v1/students/1", headers=headers).status_code == 403
