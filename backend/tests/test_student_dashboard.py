"""Regression tests for the student-specific dashboard overview."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.v1.auth import create_token
from app.api.v1.dashboard import router as dashboard_router
from app.core.database import get_session
from app.models import SysUser


def _build_client(test_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(dashboard_router, prefix="/api/v1")

    def override_session():
        yield test_session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth_header(user: SysUser) -> dict[str, str]:
    token = create_token(user.user_id, user.username)
    return {"Authorization": f"Bearer {token}"}


def test_student_overview_uses_current_students_data(session: Session):
    first_student_user = session.get(SysUser, 2)
    second_student_user = session.get(SysUser, 3)
    assert first_student_user is not None
    assert second_student_user is not None

    client = _build_client(session)
    first_response = client.get(
        "/api/v1/dashboard/student-overview",
        headers=_auth_header(first_student_user),
    )
    second_response = client.get(
        "/api/v1/dashboard/student-overview",
        headers=_auth_header(second_student_user),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()

    assert first["student"]["id"] == 1
    assert first["student"]["college"] == "计算机学院"
    assert first["summary"]["courseCount"] == 1
    assert first["summary"]["averageScore"] == 71.7
    assert first["summary"]["attendanceRate"] == 25.0
    assert first["summary"]["classRank"] == 1
    assert first["summary"]["classRankText"] == "前34%"
    assert first["summary"]["classStudentCount"] == 3
    assert first["summary"]["pendingQuizCount"] >= 0
    assert first["summary"]["weakKnowledgeCount"] >= 3

    first_course = first["courses"][0]
    assert first_course["id"] == 1
    assert first_course["name"] == "数据结构"
    assert first_course["teacher"] == "王老师"
    assert first_course["score"] == 71.7
    assert first_course["avgScore"] == 70.6
    assert first_course["rank"] == 1
    assert first_course["rankText"] == "前34%"
    assert first_course["progress"] is None or 0 <= first_course["progress"] <= 100

    assert second["student"]["id"] == 2
    assert second["summary"]["averageScore"] == 70.0
    assert second["summary"]["attendanceRate"] == 100.0
    assert second["summary"]["classRank"] == 2
    assert first["summary"] != second["summary"]


def test_student_overview_rejects_non_students_and_anonymous_users(session: Session):
    teacher_user = session.get(SysUser, 1)
    assert teacher_user is not None
    client = _build_client(session)

    assert client.get("/api/v1/dashboard/student-overview").status_code == 401
    assert client.get(
        "/api/v1/dashboard/student-overview",
        headers=_auth_header(teacher_user),
    ).status_code == 403
