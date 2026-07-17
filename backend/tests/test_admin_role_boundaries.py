"""Regression tests for administrator and teaching responsibility boundaries."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.eval_config import router as eval_config_router
from app.api.v1.logs import router as logs_router
from app.api.v1.question_bank import router as question_bank_router
from app.api.v1.scores import router as scores_router
from app.api.v1.users import router as users_router
from app.api.v1.auth import create_token
from app.core.database import get_session
from app.models import SysRole, SysUser


def _build_client(test_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(users_router, prefix="/api")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(logs_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(eval_config_router, prefix="/api/v1")
    app.include_router(question_bank_router, prefix="/api/v1")
    app.include_router(scores_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")

    def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _ensure_admin(engine) -> SysUser:
    with Session(engine) as session:
        role = session.exec(
            select(SysRole).where(SysRole.role_code == "admin")
        ).first()
        if not role:
            role = SysRole(
                role_id=99,
                role_name="系统管理员",
                role_code="admin",
            )
            session.add(role)
            session.commit()
            session.refresh(role)

        user = session.exec(
            select(SysUser).where(SysUser.username == "boundary-admin")
        ).first()
        if not user:
            user = SysUser(
                user_id=99,
                username="boundary-admin",
                password="not-used",
                real_name="边界测试管理员",
                role_id=role.role_id,
                status=1,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user


def _auth_header(user: SysUser) -> dict[str, str]:
    token = create_token(user.user_id, user.username)
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_govern_but_cannot_access_teaching_features(engine):
    admin = _ensure_admin(engine)
    with Session(engine) as session:
        teacher = session.get(SysUser, 1)
        assert teacher is not None

        session.exec(select(SysUser)).first()
        client = _build_client(session)
        admin_headers = _auth_header(admin)
        teacher_headers = _auth_header(teacher)

        assert client.get("/api/v1/admin/overview", headers=admin_headers).status_code == 200
        assert client.get("/api/users", headers=admin_headers).status_code == 200
        assert client.get("/api/v1/logs", headers=admin_headers).status_code == 200

        assert client.get("/api/v1/admin/overview", headers=teacher_headers).status_code == 403
        assert client.get("/api/users", headers=teacher_headers).status_code == 403
        assert client.get("/api/v1/logs", headers=teacher_headers).status_code == 403

        teaching_urls = [
            "/api/v1/dashboard/stats?course_id=1",
            "/api/v1/eval-config/1",
            "/api/v1/question-bank?course_id=1",
            "/api/v1/score-records?course_id=1",
            "/api/v1/agent/tools",
        ]
        for url in teaching_urls:
            assert client.get(url, headers=admin_headers).status_code == 403
            assert client.get(url, headers=teacher_headers).status_code == 200
