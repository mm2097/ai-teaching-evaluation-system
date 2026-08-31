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
from app.api.v1.auth import router as auth_router
from app.core.database import get_session
from app.core.security import hash_password
from app.models import SysOperationLog, SysRole, SysUser

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
        s.add(SysRole(role_id=2, role_name="教师", role_code="teacher"))
        s.add(SysUser(
            user_id=1, username="teacher", password=hash_password("123456"),
            real_name="王老师", role_id=2, status=1,
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
