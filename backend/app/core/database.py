from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程下使用
connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create tables and apply lightweight SQLite-compatible migrations."""
    from app import models  # noqa: F401 触发模型注册
    SQLModel.metadata.create_all(engine)
    _migrate_answer_task()
    _migrate_ai_question()
    _migrate_legacy_tables()


def _migrate_ai_question() -> None:
    """Add columns introduced after older ai_question tables were created."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "ai_question" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("ai_question")}
        if "source" not in columns:
            connection.execute(text(
                "ALTER TABLE ai_question ADD COLUMN source "
                "VARCHAR(10) NOT NULL DEFAULT 'manual'"
            ))


def _migrate_answer_task() -> None:
    """Add fields needed by assignments and self-practice to legacy answer_task tables."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "answer_task" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("answer_task")}
        if "task_type" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN task_type "
                "VARCHAR(20) NOT NULL DEFAULT 'assignment'"
            ))
        if "max_attempts" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN max_attempts "
                "INTEGER NOT NULL DEFAULT 1"
            ))
        if "allow_review" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN allow_review "
                "INTEGER NOT NULL DEFAULT 0"
            ))
        connection.execute(
            text(
                "UPDATE answer_task SET task_type = 'self_practice' "
                "WHERE task_name LIKE :prefix"
            ),
            {"prefix": "【自主练习】%"},
        )


def _migrate_answer_task_type() -> None:
    """Backward-compatible alias for older tests/imports."""
    _migrate_answer_task()


def _migrate_legacy_tables() -> None:
    """Backfill columns added while legacy SQLite databases evolved."""
    migrations = {
        "attendance_record": {
            "source_data": "ALTER TABLE attendance_record ADD COLUMN source_data TEXT",
        },
        "class_info": {
            "major": "ALTER TABLE class_info ADD COLUMN major VARCHAR(64) NOT NULL DEFAULT ''",
            "grade": "ALTER TABLE class_info ADD COLUMN grade VARCHAR(16) NOT NULL DEFAULT ''",
        },
        "exam_batch": {
            "semester": "ALTER TABLE exam_batch ADD COLUMN semester VARCHAR(32) NOT NULL DEFAULT ''",
        },
        "score_record": {
            "source_data": "ALTER TABLE score_record ADD COLUMN source_data TEXT",
        },
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        for table_name, columns in migrations.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, statement in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
        if "class_info" in table_names:
            _backfill_class_dimensions(connection)


def _backfill_class_dimensions(connection) -> None:
    """Recover major and grade from legacy class names when possible."""
    connection.execute(text(
        """
        UPDATE class_info
        SET major = CASE
            WHEN class_name LIKE '计科%' THEN '计算机科学与技术'
            WHEN class_name LIKE '软工%' OR class_name LIKE '软件%' THEN '软件工程'
            WHEN class_name LIKE '数统%' THEN '数学与应用数学'
            ELSE major
        END
        WHERE major IS NULL OR major = ''
        """
    ))
    connection.execute(text(
        """
        UPDATE class_info
        SET grade = '20' || substr(class_name, -5, 2) || '级'
        WHERE (grade IS NULL OR grade = '')
          AND class_name GLOB '*[0-9][0-9][0-9][0-9]班'
        """
    ))


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a database session."""
    with Session(engine) as session:
        yield session