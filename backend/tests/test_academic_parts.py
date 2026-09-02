"""学业水平五部分配比（小班讨论/期中/期末/考勤/其他）测试。

覆盖:
- 组成部分按批次名称关键字识别（讨论/期中/期末/其他/考勤）
- 配比加权计算与无数据部分归一化
- 配比从评价配置读取（academic_part 指标），无效配置回退默认
- 评价配置接口：「其他」指标权重自动补足 = 100 − 其余
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.api.v1.auth import create_token
from app.api.v1.eval_config import router as eval_config_router
from app.core.database import get_session
from app.models import (
    AttendanceRecord,
    AttendanceSheet,
    ClassInfo,
    Course,
    CourseStudent,
    CourseTestDetail,
    EvalDimension,
    EvalIndex,
    ExamBatch,
    IndividualScore,
    Student,
    SysRole,
    SysUser,
    Teacher,
)
from app.services.profile import (
    ACADEMIC_PARTS_DEFAULT,
    _academic_part_score,
    compute_academic_score,
    load_academic_parts,
)


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
        s.add(SysUser(user_id=1, username="teacher", password="x", real_name="王建国", role_id=2, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王建国", user_id=1, college="计算机学院"))
        s.add(ClassInfo(class_id=1, class_name="软件1801班", college="计算机学院"))
        s.add(Course(course_id=1, course_code="CS101", course_name="计算机网络",
                     teacher_id=1, semester="2025-2026-1", college="计算机学院"))
        s.add(Student(student_id=1, student_no="S001", real_name="张三", class_id=1, user_id=101))
        s.add(CourseStudent(course_id=1, student_id=1))
        # 批次：小班讨论/期中/期末（各题得分）/作业/实验
        batches = [
            ExamBatch(course_id=1, batch_name="小班讨论", batch_type=1, create_by=1),
            ExamBatch(course_id=1, batch_name="期中考试", batch_type=3, create_by=1),
            ExamBatch(course_id=1, batch_name="期末考试", batch_type=4, create_by=1),
            ExamBatch(course_id=1, batch_name="平时作业", batch_type=1, create_by=1),
            ExamBatch(course_id=1, batch_name="实验报告", batch_type=2, create_by=1),
        ]
        s.add_all(batches)
        s.commit()
        by_name = {b.batch_name: b.batch_id for b in batches}
        # 单项成绩：小班讨论 90、平时作业 80、实验报告 70
        s.add_all([
            IndividualScore(student_id=1, exam_batch_id=by_name["小班讨论"], score=90, create_by=1),
            IndividualScore(student_id=1, exam_batch_id=by_name["平时作业"], score=80, create_by=1),
            IndividualScore(student_id=1, exam_batch_id=by_name["实验报告"], score=70, create_by=1),
        ])
        # 各题得分：期中 75、期末 85
        s.add_all([
            CourseTestDetail(student_id=1, exam_batch_id=by_name["期中考试"], total_score=75, create_by=1),
            CourseTestDetail(student_id=1, exam_batch_id=by_name["期末考试"], total_score=85, create_by=1),
        ])
        # 考勤：出勤 3 次、缺勤 1 次 → 到课率 0.75
        from datetime import date as _date
        s.add_all([
            AttendanceRecord(course_id=1, student_id=1, status=0, attendance_date=_date(2025, 9, 1), create_by=1),
            AttendanceRecord(course_id=1, student_id=1, status=0, attendance_date=_date(2025, 9, 8), create_by=1),
            AttendanceRecord(course_id=1, student_id=1, status=0, attendance_date=_date(2025, 9, 15), create_by=1),
            AttendanceRecord(course_id=1, student_id=1, status=3, attendance_date=_date(2025, 9, 22), create_by=1),
        ])
        s.commit()
    return eng


def test_part_score_keyword_matching(engine):
    """五个组成部分按批次名称关键字正确识别。"""
    with Session(engine) as s:
        assert _academic_part_score(s, 1, 1, "discussion") == 90.0   # 小班讨论
        assert _academic_part_score(s, 1, 1, "midterm") == 75.0      # 期中（各题得分表）
        assert _academic_part_score(s, 1, 1, "final") == 85.0        # 期末（各题得分表）
        assert _academic_part_score(s, 1, 1, "attendance") == 75.0   # 到课率 0.75×100
        assert _academic_part_score(s, 1, 1, "other") == 75.0        # 其他 = (80+70)/2


def test_compute_academic_score_weighted(engine):
    """学业水平 = Σ(组成分 × 配比)，配比合计 100%。"""
    with Session(engine) as s:
        score = compute_academic_score(s, 1, 1)
        # 默认配比 10/30/30/10/20：
        # 0.1*90 + 0.3*75 + 0.3*85 + 0.1*75 + 0.2*75 = 9 + 22.5 + 25.5 + 7.5 + 15 = 79.5
        assert abs(score - 79.5) < 0.1


def test_compute_academic_score_normalizes_missing_parts(engine):
    """无数据的部分按配比归一化分摊。"""
    with Session(engine) as s:
        # 只给期中/期末配比（各 50），讨论/考勤/其他无数据
        score = compute_academic_score(
            s, 1, 1,
            parts={"discussion": 0, "midterm": 50, "final": 50, "attendance": 0, "other": 0},
        )
        # 讨论/考勤/其他配比为 0 不参与；期中 75 + 期末 85 → (75+85)/2 = 80
        assert score == 80.0


def test_load_academic_parts_from_config(engine):
    """配比从评价配置（academic_part 指标）读取；无效配置回退默认。"""
    with Session(engine) as s:
        dim = EvalDimension(course_id=1, dimension_name="学业成绩", sort_num=1)
        s.add(dim)
        s.commit()
        s.refresh(dim)
        s.add_all([
            EvalIndex(dimension_id=dim.dimension_id, index_name="小班讨论", weight=20,
                      score_rule='{"type":"academic_part","part":"discussion"}'),
            EvalIndex(dimension_id=dim.dimension_id, index_name="期中考试", weight=20,
                      score_rule='{"type":"academic_part","part":"midterm"}'),
            EvalIndex(dimension_id=dim.dimension_id, index_name="期末考试", weight=30,
                      score_rule='{"type":"academic_part","part":"final"}'),
            EvalIndex(dimension_id=dim.dimension_id, index_name="考勤", weight=10,
                      score_rule='{"type":"academic_part","part":"attendance"}'),
            EvalIndex(dimension_id=dim.dimension_id, index_name="其他", weight=20,
                      score_rule='{"type":"academic_part","part":"other"}'),
        ])
        s.commit()

        parts = load_academic_parts(s, 1)
        assert parts == {"discussion": 20.0, "midterm": 20.0, "final": 30.0,
                         "attendance": 10.0, "other": 20.0}

        # 合计不为 100 → 回退默认
        s.exec(select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)).first().weight = 50
        s.commit()
        assert load_academic_parts(s, 1) == ACADEMIC_PARTS_DEFAULT


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(eval_config_router, prefix="/api/v1")

    def override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(1, 'teacher')}"}


def test_other_index_weight_auto_fill(client):
    """「其他」指标权重自动补足 = 100 − 其余指标权重和。"""
    # 新建维度
    resp = client.post(
        "/api/v1/eval-config/1/dimensions",
        params={"dimension_name": "学业水平", "sort_num": 2},
        headers=_auth(),
    )
    assert resp.status_code == 200
    dim_id = resp.json()["dimensionId"]

    def add_index(name, weight, rule):
        return client.post(
            f"/api/v1/eval-config/dimensions/{dim_id}/indexes",
            params={"index_name": name, "weight": weight, "score_rule": rule},
            headers=_auth(),
        )

    add_index("小班讨论", 10, '{"type":"academic_part","part":"discussion"}')
    add_index("期中考试", 30, '{"type":"academic_part","part":"midterm"}')
    add_index("期末考试", 30, '{"type":"academic_part","part":"final"}')
    add_index("考勤", 10, '{"type":"academic_part","part":"attendance"}')
    resp = add_index("其他", 0, '{"type":"academic_part","part":"other"}')
    assert resp.status_code == 200
    # 「其他」自动补足 = 100 − (10+30+30+10) = 20
    assert resp.json()["weight"] == 20.0
    assert resp.json()["weightSumAfterAdd"] == 100.0
    assert resp.json()["weightValid"] is True

    # 修改期中权重 30 → 40，「其他」自动降为 10
    idx_list = client.get("/api/v1/eval-config/1", headers=_auth()).json()["dimensions"]
    indexes = next(d for d in idx_list if d["dimensionId"] == dim_id)["indexes"]
    midterm = next(i for i in indexes if i["indexName"] == "期中考试")
    other = next(i for i in indexes if i["indexName"] == "其他")
    resp = client.put(
        f"/api/v1/eval-config/indexes/{midterm['indexId']}",
        params={"weight": 40},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["weightValid"] is True
    resp = client.get("/api/v1/eval-config/1", headers=_auth()).json()
    indexes = next(d for d in resp["dimensions"] if d["dimensionId"] == dim_id)["indexes"]
    other = next(i for i in indexes if i["indexName"] == "其他")
    assert other["weight"] == 10.0  # 100 − (10+40+30+10) = 10

    # 其余权重和超过 100 → 拒绝
    resp = client.put(
        f"/api/v1/eval-config/indexes/{midterm['indexId']}",
        params={"weight": 70},
        headers=_auth(),
    )
    assert resp.status_code == 400
    assert "超过 100%" in resp.json()["detail"]


def test_migrate_academic_parts(monkeypatch, tmp_path):
    """启动迁移：旧「期末/平时/期中」配置 → 五部分默认；缺失维度课程自动补建。"""
    import json
    import app.core.database as db_module
    from app.models import Course

    eng = create_engine(
        f"sqlite:///{tmp_path / 'legacy.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Course(course_id=1, course_code="CS101", course_name="计算机网络",
                     teacher_id=1, semester="2025-2026-1", college="计算机学院"))
        s.add(Course(course_id=2, course_code="CS102", course_name="操作系统",
                     teacher_id=1, semester="2025-2026-1", college="计算机学院"))
        s.add(EvalDimension(dimension_id=1, course_id=1, dimension_name="学业成绩"))
        s.add(EvalIndex(dimension_id=1, index_name="期末成绩", weight=40,
                        score_rule='{"type":"direct","source":"score_record","batch_type":4}'))
        s.add(EvalIndex(dimension_id=1, index_name="平时成绩", weight=30,
                        score_rule='{"type":"direct","source":"score_record","batch_type":1}'))
        s.add(EvalIndex(dimension_id=1, index_name="期中成绩", weight=30,
                        score_rule='{"type":"direct","source":"score_record","batch_type":3}'))
        s.commit()

    monkeypatch.setattr(db_module, "engine", eng)
    db_module._migrate_academic_parts()

    with Session(eng) as s:
        # 课程1：旧指标迁移为五部分，维度更名「学业水平」
        dim1 = s.get(EvalDimension, 1)
        assert dim1.dimension_name == "学业水平"
        indexes = s.exec(select(EvalIndex).where(EvalIndex.dimension_id == 1)).all()
        names = [i.index_name for i in indexes]
        assert names == ["小班讨论", "期中考试", "期末考试", "考勤", "其他"]
        assert sum(i.weight for i in indexes) == 100.0
        parts = sorted(json.loads(i.score_rule)["part"] for i in indexes)
        assert parts == ["attendance", "discussion", "final", "midterm", "other"]
        # 课程2：无配置 → 自动补建默认维度与五部分
        dim2 = s.exec(select(EvalDimension).where(EvalDimension.course_id == 2)).first()
        assert dim2 is not None and dim2.dimension_name == "学业水平"
        indexes2 = s.exec(select(EvalIndex).where(EvalIndex.dimension_id == dim2.dimension_id)).all()
        assert len(indexes2) == 5
        assert sum(i.weight for i in indexes2) == 100.0

    # 幂等：再次执行不产生重复指标
    db_module._migrate_academic_parts()
    with Session(eng) as s:
        dims = s.exec(select(EvalDimension).where(EvalDimension.course_id == 1)).all()
        assert len(dims) == 1
        indexes = s.exec(select(EvalIndex).where(EvalIndex.dimension_id == 1)).all()
        assert len(indexes) == 5
