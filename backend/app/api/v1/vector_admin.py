"""向量索引管理 API。

接口：
    POST /api/v1/vector/rebuild  全量重建向量索引
    GET  /api/v1/vector/stats    索引统计
    POST /api/v1/vector/sync     增量同步（按课程）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import require_teacher
from app.services.rag_service import get_rag_service
from app.services.vector_store import get_vector_store

router = APIRouter(dependencies=[Depends(require_teacher)])


class RebuildRequest(BaseModel):
    """全量重建请求。"""
    courseId: int = 0  # 0 = 重建所有课程


class SyncRequest(BaseModel):
    """增量同步请求。"""
    courseId: int


@router.post("/vector/rebuild", tags=["向量索引"])
def rebuild_vector_index(
    req: RebuildRequest,
    session: Session = Depends(get_session),
) -> dict:
    """全量重建向量索引（先清空再全量嵌入）。"""
    rag = get_rag_service()
    result = rag.rebuild_index(session, course_id=req.courseId)
    return result


@router.get("/vector/stats", tags=["向量索引"])
def vector_stats() -> dict:
    """向量索引统计：各 collection 的题目数。"""
    store = get_vector_store()
    return store.get_stats()


@router.post("/vector/sync", tags=["向量索引"])
def sync_vector_index(
    req: SyncRequest,
    session: Session = Depends(get_session),
) -> dict:
    """增量同步指定课程（不清空，只补缺失的）。

    遍历该课程所有题目，逐题 upsert 到向量索引。
    """
    rag = get_rag_service()
    if not rag.vector_available:
        return {"available": False, "synced": 0, "error": "向量服务不可用"}

    from sqlmodel import select
    from app.models import AiQuestion

    questions = session.exec(
        select(AiQuestion).where(AiQuestion.course_id == req.courseId)
    ).all()

    synced = 0
    for q in questions:
        ok = rag.sync_question(session, req.courseId, q.question_id, "upsert")
        if ok:
            synced += 1

    return {
        "available": True,
        "courseId": req.courseId,
        "totalQuestions": len(questions),
        "synced": synced,
    }
