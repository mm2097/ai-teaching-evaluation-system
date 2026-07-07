from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.core.database import get_session

router = APIRouter()


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    """健康检查,同时验证数据库连通性。"""
    session.execute(text("SELECT 1"))
    return {"status": "ok"}
