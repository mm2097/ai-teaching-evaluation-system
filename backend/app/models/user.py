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
    college: Optional[str] = Field(default=None, max_length=64)  # 所属学院
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
    college: Optional[str] = Field(default=None, max_length=64)
    class_id: Optional[int] = None  # 仅学生：写入 student 表
    student_no: Optional[str] = Field(default=None, max_length=32)  # 仅学生：学号，默认与账号相同
    gender: Optional[int] = Field(default=None, ge=0, le=1)  # 仅学生：0=女, 1=男，默认男
    teacher_no: Optional[str] = Field(default=None, max_length=32)  # 仅教师：教工号，默认与账号相同
    title: Optional[str] = Field(default=None, max_length=32)  # 仅教师：职称，可空
    phone: Optional[str] = Field(default=None, max_length=20)  # 学生/教师档案：手机号，可空
    email: Optional[str] = Field(default=None, max_length=64)  # 学生/教师档案：邮箱，可空


class UserUpdate(SQLModel):
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    real_name: Optional[str] = None
    role_id: Optional[int] = None
    status: Optional[int] = None
    college: Optional[str] = Field(default=None, max_length=64)
    class_id: Optional[int] = None
    student_no: Optional[str] = Field(default=None, max_length=32)
    gender: Optional[int] = Field(default=None, ge=0, le=1)
    teacher_no: Optional[str] = Field(default=None, max_length=32)
    title: Optional[str] = Field(default=None, max_length=32)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=64)


class UserRead(SQLModel):
    user_id: int
    username: str
    real_name: str
    role_id: int
    status: int
    create_time: datetime
