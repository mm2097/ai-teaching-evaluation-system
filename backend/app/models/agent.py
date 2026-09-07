"""Persisted AI Agent conversations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class AgentConversation(SQLModel, table=True):
    """One isolated conversation context for one user and analysis target."""

    __tablename__ = "agent_conversation"

    conversation_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="sys_user.user_id", index=True)
    session_id: str = Field(index=True, max_length=255)
    course_id: Optional[int] = Field(default=None, index=True)
    student_id: Optional[int] = Field(default=None, index=True)
    agent_type: str = Field(default="qa", max_length=32)
    history_json: str = Field(default="[]", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now, index=True)
