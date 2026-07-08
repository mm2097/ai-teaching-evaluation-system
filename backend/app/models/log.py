"""操作日志模型。对应设计文档 4.7.1 节。"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SysOperationLog(SQLModel, table=True):
    """操作日志表 sys_operation_log。"""

    __tablename__ = "sys_operation_log"

    log_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="sys_user.user_id", index=True)
    module: str = Field(max_length=32)  # 如：用户管理、数据管理
    operation: str = Field(max_length=32)  # 如：新增、编辑、删除、查询
    content: str = Field(max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=64)
    operation_time: datetime = Field(default_factory=datetime.now)
