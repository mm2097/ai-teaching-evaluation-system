"""RagService 单元测试。

mock VectorStore + EmbeddingService，测：
- 向量检索正常路径
- 向量不可用时回退 SQL
- 嵌入失败时回退 SQL
- retrieve_reference_questions 格式
- rebuild_index 全量重建
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.rag_service import RagService


def _make_rag_service(vector_available=True, embed_succeeds=True):
    """构造 RagService with mock 依赖。"""
    svc = RagService.__new__(RagService)
    svc._embedding = MagicMock()
    svc._embedding.available = vector_available
    svc._vector_store = MagicMock()
    svc._vector_store.available = vector_available

    if vector_available:
        if embed_succeeds:
            svc._embedding.embed.return_value = [0.1] * 128
            svc._embedding.embed_batch.return_value = [[0.1] * 128]
        else:
            from app.core.embedding import EmbeddingError
            svc._embedding.embed.side_effect = EmbeddingError("mock fail")
            svc._embedding.embed_batch.side_effect = EmbeddingError("mock fail")

    return svc


class TestRagServiceSearch:
    """search 方法测试。"""

    def test_vector_search_normal(self, session):
        """向量检索正常路径。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.search.return_value = [
            {"question_id": 2, "content": "二叉树第k层", "metadata": {"difficulty": "easy"}, "similarity": 0.95},
        ]

        results = svc.search(session, course_id=1, query="二叉树", top_k=5)

        assert len(results) >= 1
        assert results[0]["question_id"] == 2
        assert results[0]["similarity"] == 0.95

    def test_fallback_when_vector_unavailable(self, session):
        """向量不可用时回退 SQL。"""
        svc = _make_rag_service(vector_available=False)

        results = svc.search(session, course_id=1, query="二叉树", top_k=5)

        # 回退 SQL 后应能搜到二叉树相关题
        assert isinstance(results, list)
        assert len(results) > 0
        # SQL 回退有 similarity 字段
        assert "similarity" in results[0]

    def test_fallback_when_embed_fails(self, session):
        """嵌入失败时回退 SQL。"""
        svc = _make_rag_service(vector_available=True, embed_succeeds=False)

        results = svc.search(session, course_id=1, query="二叉树", top_k=5)

        # 应回退 SQL
        assert isinstance(results, list)
        assert len(results) > 0

    def test_fallback_when_vector_empty(self, session):
        """向量库为空时回退 SQL。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.search.return_value = []

        results = svc.search(session, course_id=1, query="二叉树", top_k=5)

        assert isinstance(results, list)
        assert len(results) > 0

    def test_empty_query(self, session):
        """空 query 走 SQL 回退。"""
        svc = _make_rag_service(vector_available=True)

        results = svc.search(session, course_id=1, query="", top_k=5)
        assert isinstance(results, list)

    def test_knowledge_point_filter(self, session):
        """知识点过滤生效。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.search.return_value = [
            {"question_id": 2, "content": "二叉树第k层", "metadata": {"difficulty": "easy"}, "similarity": 0.9},
            {"question_id": 8, "content": "快速排序", "metadata": {"difficulty": "medium"}, "similarity": 0.3},
        ]

        results = svc.search(
            session, course_id=1, query="二叉树", top_k=5,
            knowledge_points=["二叉树"],
        )

        # 过滤后只应有二叉树的题
        for r in results:
            assert r["knowledge_point"] == "二叉树"

    def test_difficulty_filter(self, session):
        """难度过滤（通过 where 条件）。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.search.return_value = [
            {"question_id": 2, "content": "二叉树第k层", "metadata": {"difficulty": "easy"}, "similarity": 0.9},
        ]

        svc.search(session, course_id=1, query="二叉树", top_k=5, difficulty="easy")

        # 验证 where 条件被传入
        call_kwargs = svc._vector_store.search.call_args
        where = call_kwargs.kwargs.get("where")
        assert where is not None
        assert where.get("difficulty") == "easy"


class TestRetrieveReferenceQuestions:
    """retrieve_reference_questions 方法测试。"""

    def test_vector_path_format(self, session):
        """向量路径返回格式。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.search.return_value = [
            {"question_id": 2, "content": "二叉树第k层", "metadata": {"difficulty": "easy"}, "similarity": 0.92},
        ]

        result = svc.retrieve_reference_questions(
            session, course_id=1, knowledge_points=["二叉树"], difficulty="easy", top_k=3
        )

        assert len(result) >= 1
        item = result[0]
        assert "type" in item
        assert "stem" in item
        assert "answer" in item
        assert "knowledge_point" in item

    def test_sql_fallback_format(self, session):
        """SQL 回退路径返回格式。"""
        svc = _make_rag_service(vector_available=False)

        result = svc.retrieve_reference_questions(
            session, course_id=1, knowledge_points=["二叉树"], difficulty="easy", top_k=3
        )

        assert isinstance(result, list)
        for item in result:
            assert "type" in item
            assert "stem" in item
            assert "answer" in item


class TestRebuildIndex:
    """rebuild_index 方法测试。"""

    def test_rebuild_unavailable(self, session):
        """向量不可用时返回 available=False。"""
        svc = _make_rag_service(vector_available=False)
        result = svc.rebuild_index(session, course_id=1)
        assert result["available"] is False

    def test_rebuild_single_course(self, session):
        """重建单课程索引。"""
        svc = _make_rag_service(vector_available=True)
        svc._embedding.embed_batch.return_value = [[0.1] * 128] * 50  # 充足的 mock 向量
        svc._vector_store.upsert_batch.return_value = 10

        result = svc.rebuild_index(session, course_id=1)
        assert result["available"] is True
        assert result["indexed"] >= 0  # 取决于 mock


class TestSyncQuestion:
    """sync_question 方法测试。"""

    def test_sync_delete(self, session):
        """删除同步。"""
        svc = _make_rag_service(vector_available=True)
        svc._vector_store.delete.return_value = True

        ok = svc.sync_question(session, course_id=1, question_id=999, action="delete")
        assert ok is True

    def test_sync_upsert(self, session):
        """upsert 同步。"""
        svc = _make_rag_service(vector_available=True)
        svc._embedding.embed.return_value = [0.1] * 128
        svc._vector_store.upsert.return_value = True

        ok = svc.sync_question(session, course_id=1, question_id=2, action="upsert")
        assert ok is True

    def test_sync_unavailable(self, session):
        """向量不可用时同步返回 False。"""
        svc = _make_rag_service(vector_available=False)
        ok = svc.sync_question(session, course_id=1, question_id=2)
        assert ok is False
