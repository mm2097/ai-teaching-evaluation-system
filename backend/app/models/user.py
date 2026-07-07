"""用户模型与 API schema。

SQLModel 推荐写法:把表模型(table=True)和请求/响应 schema 放一起,
共享字段定义,减少重复。
"""
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """用户表。"""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str  # TODO: 生产环境用 passlib[bcrypt] 哈希存储,当前为明文(仅 demo)
    name: str
    role: str = Field(default="teacher", index=True)  # admin / manager / teacher / student
    department: str = Field(default="")
    status: bool = Field(default=True)  # True=启用, False=禁用
    created_at: datetime = Field(default_factory=datetime.now)


# --- API Schemas(不映射表,只用于请求/响应)---


class UserCreate(SQLModel):
    """创建用户 - 请求体。"""

    username: str
    password: str
    name: str
    role: str = "teacher"
    department: str = ""
    status: bool = True


class UserUpdate(SQLModel):
    """更新用户 - 请求体(所有字段可选,只更新传入的字段)。"""

    username: str | None = None
    password: str | None = None
    name: str | None = None
    role: str | None = None
    department: str | None = None
    status: bool | None = None


class UserRead(SQLModel):
    """返回给前端的用户信息(不含密码)。"""

    id: int
    username: str
    name: str
    role: str
    department: str
    status: bool
    created_at: datetime
