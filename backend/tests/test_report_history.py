import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.api.v1.report import _snapshot_pdf, _snapshot_workbook
from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.main import app
from app.models import (
    ClassInfo,
    Course,
    ReportHistory,
    Student,
    SysRole,
    SysUser,
    Teacher,
)


@pytest.fixture
def report_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'report-history.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(SysRole(role_id=1, role_name="教师", role_code="teacher"))
        session.add(SysRole(role_id=2, role_name="学生", role_code="student"))
        session.add(SysUser(user_id=1, username="teacher", password="secret", real_name="王老师", role_id=1))
        session.add(SysUser(user_id=2, username="student", password="secret", real_name="张三", role_id=2))
        session.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王老师", user_id=1, college="计算机学院"))
        session.add(ClassInfo(class_id=1, class_name="计科2401班", college="计算机学院", major="计算机科学与技术", grade="2024级"))
        session.add(Course(course_id=1, course_code="CS101", course_name="数据结构", teacher_id=1, semester="2024-2025-1", college="计算机学院", status=1))
        session.add(Student(student_id=1, student_no="2024001", real_name="张三", class_id=1, user_id=2))
        session.commit()
        yield session


def _client(session, user_id: int) -> TestClient:
    # Pin the fixture session to its seeded in-memory SQLite connection before
    # TestClient switches execution to a worker thread.
    user = session.get(SysUser, user_id)

    def override_session():
        yield session

    def override_user():
        return user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def _generate(client: TestClient):
    return client.post(
        "/api/v1/report/history",
        json={
            "course_id": 1,
            "report_type": 1,
            "class_id": 1,
            "semester": "2024-2025-1",
            "export_format": "pdf",
            "use_llm": False,
            "dashboard_stats": {"studentCount": 3, "passRate": 66.7},
        },
    )


def test_report_history_persists_and_downloads(report_session):
    session = report_session
    try:
        response = _generate(_client(session, 1))
        assert response.status_code == 200, response.text
        created = response.json()
        report_id = created["id"]
        assert created["parameters"]["semester"] == "2024-2025-1"
        assert created["data"]["report_type"] == 1
        assert created["stats"]["studentCount"] == 3

        # A new client/session dependency still reads the database-backed record.
        refreshed_client = _client(session, 1)
        listing = refreshed_client.get("/api/v1/report/history")
        assert listing.status_code == 200
        assert report_id in [item["id"] for item in listing.json()]

        detail = refreshed_client.get(f"/api/v1/report/history/{report_id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["summary"]

        download = refreshed_client.get(
            f"/api/v1/report/history/{report_id}/download",
            params={"format": "xlsx"},
        )
        assert download.status_code == 200
        assert download.content.startswith(b"PK")
        assert "spreadsheetml" in download.headers["content-type"]

        pdf_download = refreshed_client.get(
            f"/api/v1/report/history/{report_id}/download",
            params={"format": "pdf"},
        )
        assert pdf_download.status_code == 200
        assert pdf_download.content.startswith(b"%PDF")
        assert pdf_download.headers["content-type"] == "application/pdf"
    finally:
        app.dependency_overrides.clear()


def test_report_history_is_private_to_creator(report_session):
    session = report_session
    try:
        created = _generate(_client(session, 1))
        assert created.status_code == 200
        report_id = created.json()["id"]

        student_client = _client(session, 2)
        assert student_client.get(f"/api/v1/report/history/{report_id}").status_code == 403
        student_listing = student_client.get("/api/v1/report/history")
        assert student_listing.status_code == 200
        assert report_id not in [item["id"] for item in student_listing.json()]
    finally:
        app.dependency_overrides.clear()


def test_snapshot_workbook_uses_saved_content():
    history = ReportHistory(
        creator_user_id=1,
        course_id=1,
        report_type=1,
        scope="class",
        class_id=1,
        export_format="xlsx",
        report_name="快照报告",
        course_name="数据结构",
        parameter_snapshot="{}",
        report_snapshot=(
            '{"summary":"保存时摘要","conclusion":"保存时结论",'
            '"suggestion":"保存时建议"}'
        ),
        stats_snapshot='{"passRate":88}',
    )
    content = _snapshot_workbook(history)
    assert content.startswith(b"PK")
    pdf_content = _snapshot_pdf(history)
    assert pdf_content.startswith(b"%PDF")
    assert len(pdf_content) > 2000
