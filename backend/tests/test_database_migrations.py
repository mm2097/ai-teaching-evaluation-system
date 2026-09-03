"""旧 SQLite 数据库结构升级测试。"""
from sqlalchemy import create_engine, inspect, text

from app.core import database


def test_migrate_legacy_tables_adds_missing_columns(monkeypatch):
    migration_engine = create_engine("sqlite:///:memory:")
    with migration_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE attendance_record (attendance_id INTEGER PRIMARY KEY)"
        ))
        connection.execute(text(
            "CREATE TABLE class_info ("
            "class_id INTEGER PRIMARY KEY, class_name VARCHAR(64) NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO class_info (class_id, class_name) VALUES "
            "(1, '计科2401班'), (2, '软件1802班')"
        ))
        connection.execute(text(
            "CREATE TABLE exam_batch (batch_id INTEGER PRIMARY KEY)"
        ))
        connection.execute(text(
            "CREATE TABLE score_record (score_id INTEGER PRIMARY KEY)"
        ))
        connection.execute(text(
            "CREATE TABLE sys_user (user_id INTEGER PRIMARY KEY)"
        ))

    monkeypatch.setattr(database, "engine", migration_engine)
    database._migrate_legacy_tables()
    database._migrate_legacy_tables()

    inspector = inspect(migration_engine)
    assert "source_data" in {
        column["name"] for column in inspector.get_columns("attendance_record")
    }
    assert {"major", "grade"} <= {
        column["name"] for column in inspector.get_columns("class_info")
    }
    assert "semester" in {
        column["name"] for column in inspector.get_columns("exam_batch")
    }
    assert "source_data" in {
        column["name"] for column in inspector.get_columns("score_record")
    }
    assert "college" in {
        column["name"] for column in inspector.get_columns("sys_user")
    }
    with migration_engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT major, grade FROM class_info ORDER BY class_id"
        )).all()
    assert rows == [
        ("计算机科学与技术", "2024级"),
        ("软件工程", "2018级"),
    ]


def test_migrate_evaluation_levels_rewrites_legacy_labels(monkeypatch):
    """存量评价等级按五档标准（优秀/良好/中等/合格/不合格）从总分重算。"""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine, Session as SqlSession, select

    from app import models  # noqa: F401
    from app.models import Course, StudentEvaluationResult

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with SqlSession(eng) as s:
        s.add(Course(course_id=1, course_code="CS101", course_name="数据结构",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院"))
        # 旧标准遗留等级 + 种子混杂数据，总分对应新标准等级
        s.add(StudentEvaluationResult(course_id=1, student_id=1, total_score=89.5, eval_level="优秀"))  # → 良好
        s.add(StudentEvaluationResult(course_id=1, student_id=2, total_score=72.0, eval_level="中"))    # → 中等
        s.add(StudentEvaluationResult(course_id=1, student_id=3, total_score=52.5, eval_level="不及格"))  # → 不合格
        s.add(StudentEvaluationResult(course_id=1, student_id=4, total_score=95.0, eval_level="优秀"))  # 不变
        s.commit()

    monkeypatch.setattr(database, "engine", eng)
    database._migrate_evaluation_levels()
    database._migrate_evaluation_levels()  # 幂等

    with SqlSession(eng) as s:
        rows = {r.student_id: r.eval_level for r in s.exec(select(StudentEvaluationResult)).all()}
    assert rows == {
        1: "良好",
        2: "中等",
        3: "不合格",
        4: "优秀",
    }
