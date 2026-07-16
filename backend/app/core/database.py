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
    """建表。新增 Model 后,在 app/models/__init__.py 里 import 即可被自动建表。"""
    from app import models  # noqa: F401  触发模型注册
    SQLModel.metadata.create_all(engine)
    _migrate_answer_task()
    _migrate_legacy_tables()



def _migrate_answer_task() -> None:
    """为 create_all 无法升级的旧 answer_task 表补齐新增字段。"""
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


def _migrate_legacy_tables() -> None:
    """补齐旧 SQLite 数据库在模型演进中新增的字段。"""
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
    """从旧班级名称中恢复专业与年级，避免字典筛选项为空。"""
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
    """FastAPI 依赖:注入数据库会话。"""
    with Session(engine) as session:
        yield session
