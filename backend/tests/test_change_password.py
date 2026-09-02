"""修改本人密码接口测试。

覆盖:
- 未登录 → 401
- 原密码错误 → 400
- 新密码过短 → 400
- 新密码与原密码相同 → 400
- 修改成功 → 新密码可登录、旧密码失效
- 修改密码操作写入系统日志
"""
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401  确保所有表注册到 metadata
from app.api.v1.auth import create_token, router as auth_router
from app.core.database import get_session
from app.core.security import hash_password
from app.models import ClassInfo, Student, SysOperationLog, SysRole, SysUser, Teacher

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(SysRole(role_id=1, role_name="管理员", role_code="admin"))
        s.add(SysRole(role_id=2, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=3, role_name="学生", role_code="student"))
        s.add(ClassInfo(class_id=1, class_name="软件1801班", college="计算机学院"))
        s.add(SysUser(
            user_id=1, username="teacher", password=hash_password("123456"),
            real_name="王老师", role_id=2, status=1,
        ))
        s.add(SysUser(
            user_id=2, username="student1", password=hash_password("123456"),
            real_name="赵同学", role_id=3, status=1,
        ))
        s.add(SysUser(
            user_id=3, username="admin", password=hash_password("123456"),
            real_name="管理员", role_id=1, status=1,
        ))
        s.add(Teacher(
            teacher_id=1, teacher_no="T001", real_name="王老师",
            college="计算机学院", user_id=1,
        ))
        s.add(Student(
            student_id=1, student_no="S001", real_name="赵同学",
            class_id=1, user_id=2,
        ))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _login(client, password: str):
    return client.post("/api/login", json={"username": "teacher", "password": password})


def _auth(client) -> dict[str, str]:
    """登录获取 Bearer 头。"""
    resp = _login(client, "123456")
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_change_password_requires_login(client):
    """未登录调用 → 401。"""
    resp = client.post("/api/password/change", json={
        "old_password": "123456", "new_password": "abc123",
    })
    assert resp.status_code == 401


def test_change_password_wrong_old_password(client):
    """原密码错误 → 400。"""
    resp = client.post("/api/password/change", json={
        "old_password": "wrong", "new_password": "abc123",
    }, headers=_auth(client))
    assert resp.status_code == 400
    assert "原密码错误" in resp.json()["detail"]


def test_change_password_too_short(client):
    """新密码少于 6 位 → 400。"""
    resp = client.post("/api/password/change", json={
        "old_password": "123456", "new_password": "123",
    }, headers=_auth(client))
    assert resp.status_code == 400
    assert "6 位" in resp.json()["detail"]


def test_change_password_same_as_old(client):
    """新密码与原密码相同 → 400。"""
    resp = client.post("/api/password/change", json={
        "old_password": "123456", "new_password": "123456",
    }, headers=_auth(client))
    assert resp.status_code == 400
    assert "相同" in resp.json()["detail"]


def test_change_password_success(client, engine):
    """修改成功 → 旧密码登录失败、新密码登录成功，并写入操作日志。"""
    headers = _auth(client)
    resp = client.post("/api/password/change", json={
        "old_password": "123456", "new_password": "newpass888",
    }, headers=headers)
    assert resp.status_code == 200

    # 旧密码失效
    old_login = _login(client, "123456")
    assert old_login.status_code == 401
    # 新密码可登录
    new_login = _login(client, "newpass888")
    assert new_login.status_code == 200

    # 操作留痕
    with Session(engine) as s:
        log = s.exec(
            select(SysOperationLog).where(SysOperationLog.operation == "修改密码")
        ).first()
        assert log is not None
        assert "teacher" in log.content


def _student_auth(client) -> dict[str, str]:
    """学生登录获取 Bearer 头。"""
    resp = client.post("/api/login", json={"username": "student1", "password": "123456"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_update_contact_for_teacher(client, engine):
    """教师可更新本人手机号/邮箱，写入教师表。"""
    # 直接签发教师 token（前面用例已修改教师密码，不能再用旧密码登录）
    headers = {"Authorization": f"Bearer {create_token(1, 'teacher')}"}
    resp = client.put("/api/profile/contact", json={
        "phone": "13800000000", "email": "t@hunnu.edu.cn",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13800000000"
    assert resp.json()["email"] == "t@hunnu.edu.cn"

    with Session(engine) as s:
        teacher = s.exec(select(Teacher).where(Teacher.user_id == 1)).first()
        assert teacher.phone == "13800000000"
        assert teacher.email == "t@hunnu.edu.cn"


def test_update_contact_forbidden_for_admin(client):
    """管理员（无学生/教师档案）修改联系方式 → 403。"""
    headers = {"Authorization": f"Bearer {create_token(3, 'admin')}"}
    resp = client.put("/api/profile/contact", json={
        "phone": "13800000000", "email": "a@hunnu.edu.cn",
    }, headers=headers)
    assert resp.status_code == 403


def test_update_contact_success(client, engine):
    """学生可更新本人手机号/邮箱，写入学生表。"""
    resp = client.put("/api/profile/contact", json={
        "phone": "13800000000", "email": "stu@hunnu.edu.cn",
    }, headers=_student_auth(client))
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13800000000"
    assert resp.json()["email"] == "stu@hunnu.edu.cn"

    with Session(engine) as s:
        student = s.exec(select(Student).where(Student.student_no == "S001")).first()
        assert student.phone == "13800000000"
        assert student.email == "stu@hunnu.edu.cn"


def test_update_contact_clear_by_empty_string(client):
    """传空串 → 清空对应联系方式。"""
    resp = client.put("/api/profile/contact", json={
        "phone": "", "email": None,
    }, headers=_student_auth(client))
    assert resp.status_code == 200
    assert resp.json()["phone"] is None
