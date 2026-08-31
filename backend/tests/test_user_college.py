"""用户创建/编辑的所属学院字段测试。

覆盖:
- 创建时不填学院 → 默认计算机学院
- 创建时填学院 → 按填写值保存
- 编辑更新学院
- 老数据(未填学院)回退到教师档案的学院
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  确保所有表注册到 metadata
from app.api.v1.auth import create_token
from app.api.v1.users import router as users_router
from app.core.database import get_session
from app.models import ClassInfo, SysRole, SysUser, Teacher


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(SysRole(role_id=1, role_name="系统管理员", role_code="admin"))
        s.add(SysRole(role_id=2, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=3, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="admin", password="x", real_name="管理员", role_id=1, status=1))
        s.add(SysUser(user_id=2, username="oldteacher", password="x", real_name="老教师", role_id=2, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="老教师", user_id=2, college="数学学院"))
        s.add(ClassInfo(class_id=1, class_name="计科2401班", college="计算机学院", major="计算机科学与技术", grade="2024级"))
        s.add(ClassInfo(class_id=2, class_name="软件1801班", college="计算机学院", major="软件工程", grade="2018级"))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(users_router, prefix="/api")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'admin')}"}


def _create(client, **kwargs):
    payload = {
        "username": kwargs.get("username", "newuser"),
        "password": "123456",
        "real_name": kwargs.get("real_name", "新用户"),
        "role_id": kwargs.get("role_id", 2),
    }
    if "college" in kwargs:
        payload["college"] = kwargs["college"]
    if "class_id" in kwargs:
        payload["class_id"] = kwargs["class_id"]
    return client.post("/api/users", json=payload, headers=_auth())


def test_create_user_without_college_defaults(client):
    """创建时不传学院 → 默认计算机学院。"""
    resp = _create(client, username="t_none")
    assert resp.status_code == 201
    assert resp.json()["department"] == "计算机学院"


def test_create_user_with_empty_college_defaults(client):
    """创建时传空字符串 → 默认计算机学院。"""
    resp = _create(client, username="t_empty", college="")
    assert resp.status_code == 201
    assert resp.json()["department"] == "计算机学院"


def test_create_user_with_college(client):
    """创建时填学院 → 按填写值保存。"""
    resp = _create(client, username="t_math", college="数学学院")
    assert resp.status_code == 201
    assert resp.json()["department"] == "数学学院"


def test_update_user_college(client):
    """编辑用户可更新学院。"""
    created = _create(client, username="t_upd", college="物理学院")
    user_id = created.json()["user_id"]
    resp = client.put(f"/api/users/{user_id}", json={"college": "化学学院"}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["department"] == "化学学院"


def test_legacy_user_falls_back_to_teacher_college(client):
    """老数据(用户表未填学院)回退到教师档案学院。"""
    resp = client.get("/api/users", headers=_auth())
    assert resp.status_code == 200
    by_username = {u["username"]: u for u in resp.json()}
    assert by_username["oldteacher"]["department"] == "数学学院"


def test_create_student_requires_class(client):
    resp = _create(client, username="stu_none", role_id=3)
    assert resp.status_code == 400
    assert "所属班级" in resp.json()["detail"]


def test_create_student_with_class(client):
    resp = _create(client, username="stu_ok", role_id=3, class_id=1)
    assert resp.status_code == 201
    body = resp.json()
    assert body["class_id"] == 1
    assert body["class_name"] == "计科2401班"
    assert body["role_code"] == "student"


def test_list_users_filter_by_class(client):
    _create(client, username="stu_a", role_id=3, class_id=1)
    _create(client, username="stu_b", role_id=3, class_id=2)
    resp = client.get("/api/users", params={"class_id": 2}, headers=_auth())
    assert resp.status_code == 200
    names = {u["username"] for u in resp.json()}
    assert "stu_b" in names
    assert "stu_a" not in names


def test_update_student_class(client):
    created = _create(client, username="stu_move", role_id=3, class_id=1)
    user_id = created.json()["user_id"]
    resp = client.put(f"/api/users/{user_id}", json={"class_id": 2}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["class_id"] == 2
    assert resp.json()["class_name"] == "软件1801班"
