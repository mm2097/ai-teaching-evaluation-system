"""课堂参与模板导入与学情画像（到课率/参与度/态度）测试。

覆盖:
- 课堂参与测试数据导入 → ParticipationSheet 落库 + 批次创建（batch_type=6）
- 教学数据查询 data_type=participation → 返回课堂参与度
- 画像：到课率优先读 AttendanceSheet；态度 = 0.5×考勤 + 0.5×课堂参与度
- 画像接口：学生视角返回五轴雷达；班级视角返回班级平均
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401  确保所有表注册到 metadata
from app.api.v1.analysis import router as analysis_router
from app.api.v1.auth import create_token
from app.api.v1.teaching_data import router as teaching_data_router
from app.core.database import get_session
from app.models import (
    AttendanceSheet,
    ClassInfo,
    Course,
    CourseStudent,
    ExamBatch,
    ParticipationSheet,
    Student,
    StudentProfile,
    SysRole,
    SysUser,
    Teacher,
)
from app.services.file_import import import_file
from app.services.profile import (
    compute_attitude_score,
    compute_profile,
)

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "测试数据")


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
        s.add(SysUser(user_id=1, username="teacher", password="x", real_name="王建国", role_id=2, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王建国", user_id=1, college="计算机学院"))
        s.add(ClassInfo(class_id=1, class_name="软件1801班", college="计算机学院"))
        s.add(ClassInfo(class_id=2, class_name="软件1802班", college="计算机学院"))
        s.add(Course(course_id=1, course_code="CS101", course_name="计算机网络",
                     teacher_id=1, semester="2025-2026-1", college="计算机学院"))
        # 与课堂参与测试数据中前 3 名学号一致
        for idx, no in enumerate(["201726010101", "201803030311", "201826010102"], start=1):
            s.add(Student(student_id=idx, student_no=no, real_name=f"学生{idx}", class_id=1, user_id=100 + idx))
            s.add(CourseStudent(course_id=1, student_id=idx))
        s.commit()
    return eng


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(teaching_data_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _teacher_auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'teacher')}"}


def test_import_participation_file(engine):
    """课堂参与测试数据导入 → ParticipationSheet 落库。"""
    file_path = os.path.join(TEST_DATA_DIR, "计算机网络课堂参与情况测试数据.xlsx")
    assert os.path.exists(file_path), f"测试数据不存在: {file_path}"

    with Session(engine) as s:
        result = import_file(s, file_path, ".xlsx", course_id=1, create_by=1)
        # 测试库仅建档了测试数据中的前 3 名学生，其余行报"学号不存在"属预期
        assert result.success_count == 3
        assert all("不存在" in e.message for e in result.errors)
        assert "课堂参与情况" in result.detected_template

    with Session(engine) as s:
        sheets = s.exec(select(ParticipationSheet)).all()
        assert len(sheets) == 3
        by_student = {p.student_id: p for p in sheets}
        # 学号 201726010101（孔祥宁）的参与度为 0.90625
        first = by_student[1]
        assert first.participation_rate == 0.90625
        assert first.participation_1 == "是"
        # 批次 batch_type=6（课堂参与）
        batch = s.get(ExamBatch, first.exam_batch_id)
        assert batch.batch_type == 6
        assert batch.batch_name == "计算机网络-课堂参与情况"


def test_query_teaching_data_participation(client):
    """教学数据查询支持 data_type=participation，返回课堂参与度。"""
    resp = client.get(
        "/api/v1/teaching-data",
        params={"course_id": 1, "data_type": "participation"},
        headers=_teacher_auth(),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3
    assert all(row["dataType"] == "participation" for row in data)
    assert all("participationRate" in row for row in data)


def test_attendance_rate_prefers_new_table(engine):
    """到课率优先读 AttendanceSheet（上传的考勤数据）。"""
    with Session(engine) as s:
        batch = s.exec(
            select(ExamBatch).where(ExamBatch.course_id == 1, ExamBatch.batch_type == 5)
        ).first()
        if not batch:
            batch = ExamBatch(course_id=1, batch_name="计算机网络-考勤情况",
                              batch_type=5, semester="2025-2026-1", create_by=1)
            s.add(batch)
            s.commit()
            s.refresh(batch)
        s.add(AttendanceSheet(
            student_id=1, exam_batch_id=batch.batch_id,
            attendance_rate=0.8, total_count=32, present_count=26,
            create_by=1,
        ))
        s.commit()

        from app.services.profile import _attendance_rate
        rate = _attendance_rate(s, 1, 1)
        assert rate == 0.8  # 新表优先，不再用旧表


def test_attitude_score_half_attendance_half_participation(engine):
    """学习态度 = 0.5×到课率 + 0.5×课堂参与度。"""
    with Session(engine) as s:
        # 学生1：到课率 0.8、参与度 0.90625 → 态度 = 0.5*80 + 0.5*90.625 = 85.3125
        score, detail = compute_attitude_score(s, 1, 1)
        assert abs(score - (0.5 * 80.0 + 0.5 * 90.625)) < 0.01
        assert detail["attendance_rate"] == 0.8
        assert detail["participation_rate"] == 0.906  # round(0.90625, 3) = 0.906
        # 互动得分 = 参与度×100（保留 1 位小数 → 90.6）
        assert abs(detail["interaction_score"] - 90.6) < 0.01


def test_profile_includes_participation_rate(engine):
    """compute_profile 返回参与度字段。"""
    with Session(engine) as s:
        p = compute_profile(s, 1, 1)
        assert p.participation_rate == 0.906
        assert p.attendance_rate == 0.8


def test_profile_radar_student_view(client, engine):
    """画像接口学生视角：返回五轴 radarIndicators + 对齐的 radarValues。"""
    with Session(engine) as s:
        s.add(StudentProfile(
            course_id=1, student_id=1,
            academic_score=82.0, attitude_score=86.9, progress_score=75.0,
            total_profile_score=81.0,
        ))
        s.commit()

    resp = client.get(
        "/api/v1/analysis/profile",
        params={"student_id": 1, "course_id": 1},
        headers=_teacher_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["viewType"] == "student"
    assert [i["name"] for i in body["radarIndicators"]] == ["成绩", "考勤", "互动", "进步", "综合"]
    values = body["radarValues"]
    assert len(values) == 5
    # 考勤轴 = 到课率×100；互动轴 = 参与度×100
    assert values[1] == 80.0
    assert abs(values[2] - 90.6) < 0.1


def test_profile_radar_class_view(client, engine):
    """画像接口班级视角：返回班级平均雷达（平均到课率/平均参与度）。"""
    # 自包含数据：清空既有考勤/参与记录后，写入 3 名学生的到课率 0.8/0.9/1.0
    with Session(engine) as s:
        for m in s.exec(select(AttendanceSheet)).all():
            s.delete(m)
        for m in s.exec(select(ParticipationSheet)).all():
            s.delete(m)
        s.commit()
        batch = ExamBatch(course_id=1, batch_name="班级平均测试批次",
                          batch_type=5, semester="2025-2026-1", create_by=1)
        s.add(batch)
        s.commit()
        s.refresh(batch)
        for sid, att in [(1, 0.8), (2, 0.9), (3, 1.0)]:
            s.add(AttendanceSheet(
                student_id=sid, exam_batch_id=batch.batch_id,
                attendance_rate=att, create_by=1,
            ))
        for sid, part in [(1, 0.8), (2, 0.9), (3, 1.0)]:
            s.add(ParticipationSheet(
                student_id=sid, exam_batch_id=batch.batch_id,
                participation_rate=part, create_by=1,
            ))
        s.commit()

    resp = client.get(
        "/api/v1/analysis/profile",
        params={"student_id": 1, "course_id": 1, "class_id": 1},
        headers=_teacher_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["viewType"] == "class"
    assert "班级平均" in body["studentName"]
    assert [i["name"] for i in body["radarIndicators"]] == ["成绩", "考勤", "互动", "进步", "综合"]
    values = body["radarValues"]
    # 平均到课率 = (0.8+0.9+1.0)/3 = 0.9 → 90.0；平均参与度同理 → 90.0
    assert values[1] == 90.0
    assert abs(values[2] - 90.0) < 0.1
