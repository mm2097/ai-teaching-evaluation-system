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
    _migrate_ai_question()


def _migrate_ai_question() -> None:
    """为旧 ai_question 表补齐 source 字段（create_all 不改已存在表）。"""
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




def _migrate_answer_task_type() -> None:
    """Backward-compatible alias for older tests/imports."""
    _migrate_answer_task()

def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖:注入数据库会话。"""
    with Session(engine) as session:
        yield session
