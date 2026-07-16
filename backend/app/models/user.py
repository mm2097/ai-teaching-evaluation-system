"""用户与角色模型。对应设计文档 4.1 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class SysRole(SQLModel, table=True):
    """角色表 sys_role。"""

    __tablename__ = "sys_role"

    role_id: Optional[int] = Field(default=None, primary_key=True)
    role_name: str = Field(max_length=32)
    role_code: str = Field(max_length=32, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=255)
    create_time: datetime = Field(default_factory=datetime.now)

    users: list["SysUser"] = Relationship(back_populates="role")


class SysUser(SQLModel, table=True):
    """系统用户表 sys_user。"""

    __tablename__ = "sys_user"

    user_id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=64, unique=True, index=True)
    password: str = Field(max_length=128)
    real_name: str = Field(max_length=32)
    role_id: int = Field(foreign_key="sys_role.role_id", index=True)
    status: int = Field(default=1)  # 0=禁用, 1=启用
    create_time: datetime = Field(default_factory=datetime.now)
    update_time: datetime = Field(default_factory=datetime.now)

    role: Optional[SysRole] = Relationship(back_populates="users")


# --- API Schemas ---


class LoginRequest(SQLModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(SQLModel):
    username: str
    password: str = Field(min_length=6, max_length=128)
    real_name: str
    role_id: int
    status: int = 1


class UserUpdate(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    real_name: Optional[str] = None
    role_id: Optional[int] = None
    status: Optional[int] = None


class UserRead(SQLModel):
    user_id: int
    username: str
    real_name: str
    role_id: int
    status: int
    create_time: datetime
