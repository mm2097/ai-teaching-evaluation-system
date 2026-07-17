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
    with migration_engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT major, grade FROM class_info ORDER BY class_id"
        )).all()
    assert rows == [
        ("计算机科学与技术", "2024级"),
        ("软件工程", "2018级"),
    ]
