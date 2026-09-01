"""学生档案新增/编辑班级/删除测试。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.api.v1.auth import create_token
from app.api.v1.students import router as students_router
from app.core.database import get_session
from app.models import ClassInfo, Student, SysRole, SysUser


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
        s.add(SysRole(role_id=3, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="admin", password="x", real_name="管理员", role_id=1, status=1))
        s.add(SysUser(user_id=10, username="stu10", password="x", real_name="学生甲", role_id=3, status=1))
        s.add(SysUser(user_id=11, username="stu11", password="x", real_name="学生乙", role_id=3, status=1))
        s.add(ClassInfo(class_id=1, class_name="计科2401班", college="计算机学院", major="计科", grade="2024级"))
        s.add(ClassInfo(class_id=2, class_name="软件1801班", college="计算机学院", major="软工", grade="2018级"))
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


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'admin')}"}


def test_create_student_profile(client):
    resp = client.post(
        "/api/v1/students",
        json={"user_id": 10, "class_id": 1},
        headers=_auth(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == 10
    assert body["class_id"] == 1
    assert body["class_name"] == "计科2401班"
    assert body["student_no"] == "stu10"


def test_create_student_duplicate_user(client):
    resp = client.post(
        "/api/v1/students",
        json={"user_id": 10, "class_id": 1},
        headers=_auth(),
    )
    assert resp.status_code == 400


def test_update_student_class(client, engine):
    with Session(engine) as s:
        student = s.exec(select(Student).where(Student.user_id == 10)).first()
        assert student is not None
        student_id = student.student_id
    resp = client.put(
        f"/api/v1/students/{student_id}",
        json={"class_id": 2},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["class_id"] == 2
    assert resp.json()["class_name"] == "软件1801班"


def test_delete_student_profile(client):
    created = client.post(
        "/api/v1/students",
        json={"user_id": 11, "class_id": 1},
        headers=_auth(),
    )
    assert created.status_code == 201
    student_id = created.json()["student_id"]
    resp = client.delete(f"/api/v1/students/{student_id}", headers=_auth())
    assert resp.status_code == 204
    missing = client.get(f"/api/v1/students/{student_id}")
    assert missing.status_code == 404
