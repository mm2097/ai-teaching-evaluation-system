from collections.abc import Generator

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


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖:注入数据库会话。"""
    with Session(engine) as session:
        yield session
