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
    # 旧库缺 exam_time 曾导致评价实时重算 500（no such column: exam_batch.exam_time）
    assert "exam_time" in {
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


def test_migrate_dimension_weight_backfills_and_creates_attitude(monkeypatch):
    """eval_dimension 增加 weight 列：回填默认占比 + 补建缺省「学习态度」维度（幂等）。"""
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine, Session as SqlSession, select

    from app import models  # noqa: F401
    from app.models import Course, EvalDimension, EvalIndex

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    # 模拟旧库：eval_dimension 无 weight 列
    with eng.begin() as connection:
        connection.execute(text("DROP TABLE eval_dimension"))
        connection.execute(text(
            "CREATE TABLE eval_dimension ("
            "dimension_id INTEGER PRIMARY KEY, course_id INTEGER, "
            "dimension_name VARCHAR(32) NOT NULL, description VARCHAR(255), "
            "sort_num INTEGER NOT NULL, create_time DATETIME, update_time DATETIME)"
        ))
    with SqlSession(eng) as s:
        s.add(Course(course_id=1, course_code="CS101", course_name="数据结构",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院"))
        s.add(Course(course_id=2, course_code="CS102", course_name="操作系统",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院"))
        s.commit()
    # 旧表无 weight 列，用原生 SQL 插入（SQLModel INSERT 会带 weight 列）
    with eng.begin() as connection:
        for dim_id, course_id, name, sort_num in [
            (1, 1, "学业水平", 1),
            (2, 1, "学习态度", 2),
            (3, 1, "学习进步", 3),
            (4, 2, "学业水平", 1),
        ]:
            connection.execute(text(
                "INSERT INTO eval_dimension "
                "(dimension_id, course_id, dimension_name, sort_num) "
                "VALUES (:dim_id, :course_id, :name, :sort_num)"
            ), {"dim_id": dim_id, "course_id": course_id, "name": name, "sort_num": sort_num})

    refreshed: list[int] = []
    monkeypatch.setattr(
        "app.services.analysis_refresh.refresh_course_evaluations",
        lambda session, course_id: refreshed.append(course_id),
    )
    monkeypatch.setattr(database, "engine", eng)
    database._migrate_dimension_weight()
    database._migrate_dimension_weight()  # 幂等

    inspector = inspect(eng)
    assert "weight" in {
        column["name"] for column in inspector.get_columns("eval_dimension")
    }
    with SqlSession(eng) as s:
        dims = {d.dimension_id: (d.course_id, d.dimension_name, d.weight)
                for d in s.exec(select(EvalDimension)).all()}
        # 回填：学业水平 60 / 学习态度 40 / 学习进步 0
        assert dims[1] == (1, "学业水平", 60.0)
        assert dims[2] == (1, "学习态度", 40.0)
        assert dims[3] == (1, "学习进步", 0.0)
        # 课程 2 缺学习态度 → 自动补建（weight 40 + 三个标准指标 40/30/30）
        course2_dims = [d for d in dims.values() if d[0] == 2]
        assert len(course2_dims) == 2
        created = next(d for d in course2_dims if d[1] == "学习态度")
        assert created[2] == 40.0
        created_id = next(
            d.dimension_id for d in s.exec(select(EvalDimension)).all()
            if d.course_id == 2 and d.dimension_name == "学习态度"
        )
        idx_weights = sorted(
            idx.weight for idx in s.exec(
                select(EvalIndex).where(EvalIndex.dimension_id == created_id)
            ).all()
        )
        assert idx_weights == [30.0, 30.0, 40.0]
        # 学业水平（课程2）保持 60
        academic2 = next(d for d in course2_dims if d[1] == "学业水平")
        assert academic2[2] == 60.0
    assert sorted(refreshed) == [1, 2]
