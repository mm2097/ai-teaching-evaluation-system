"""VectorStore 单元测试。

用临时目录创建 ChromaDB，测：
- upsert / search / delete / 按课程隔离 / count / get_stats
- ChromaDB 不可用时优雅降级
"""
from __future__ import annotations

import os
import tempfile

import pytest

from app.services.vector_store import VectorStore


@pytest.fixture
def temp_store():
    """临时目录 VectorStore（每测一个）。"""
    import shutil
    tmpdir = tempfile.mkdtemp()
    store = VectorStore(persist_path=tmpdir, dim=128)
    yield store
    # Windows 上 ChromaDB 会锁文件，忽略清理错误
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass


class TestVectorStore:
    """VectorStore 核心测试。"""

    def test_upsert_and_search(self, temp_store):
        """插入题目后能检索到。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        ok = temp_store.upsert(
            course_id=1, question_id=101,
            content="二叉树的第k层最多有多少个节点",
            embedding=[0.1] * 128,
            metadata={"knowledge_point": "二叉树", "difficulty": "easy"},
        )
        assert ok is True
        assert temp_store.count(course_id=1) == 1

        results = temp_store.search(course_id=1, query_embedding=[0.1] * 128, top_k=5)
        assert len(results) == 1
        assert results[0]["question_id"] == 101
        assert results[0]["similarity"] > 0.9  # 完全相似

    def test_upsert_overwrite(self, temp_store):
        """同 ID upsert 应覆盖。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 201, "旧内容", [0.1] * 128)
        temp_store.upsert(1, 201, "新内容", [0.2] * 128)
        assert temp_store.count(course_id=1) == 1

    def test_delete(self, temp_store):
        """删除后搜不到。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 301, "测试删除", [0.5] * 128)
        assert temp_store.count(course_id=1) == 1

        ok = temp_store.delete(1, 301)
        assert ok is True
        assert temp_store.count(course_id=1) == 0

    def test_course_isolation(self, temp_store):
        """不同课程的 collection 隔离。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 401, "课程1的题", [0.1] * 128)
        temp_store.upsert(2, 402, "课程2的题", [0.1] * 128)

        assert temp_store.count(course_id=1) == 1
        assert temp_store.count(course_id=2) == 1

        # 在课程1搜，不应返回课程2的题
        results = temp_store.search(course_id=1, query_embedding=[0.1] * 128, top_k=10)
        assert all(r["question_id"] == 401 for r in results)

    def test_top_k_limit(self, temp_store):
        """top_k 限制返回数量。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        for i in range(10):
            temp_store.upsert(1, 500 + i, f"题目{i}", [0.3] * 128)

        results = temp_store.search(course_id=1, query_embedding=[0.3] * 128, top_k=3)
        assert len(results) <= 3

    def test_where_filter_difficulty(self, temp_store):
        """metadata where 过滤（难度）。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 601, "简单题", [0.1] * 128, {"difficulty": "easy"})
        temp_store.upsert(1, 602, "难题", [0.1] * 128, {"difficulty": "hard"})

        results = temp_store.search(
            course_id=1, query_embedding=[0.1] * 128, top_k=5,
            where={"difficulty": "hard"},
        )
        assert all(r["metadata"].get("difficulty") == "hard" for r in results)

    def test_search_empty_collection(self, temp_store):
        """空 collection 搜索返回空列表。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        results = temp_store.search(course_id=999, query_embedding=[0.1] * 128, top_k=5)
        assert results == []

    def test_upsert_batch(self, temp_store):
        """批量插入。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        items = [
            {"question_id": 701, "content": "题A", "embedding": [0.1] * 128, "metadata": {"difficulty": "easy"}},
            {"question_id": 702, "content": "题B", "embedding": [0.2] * 128, "metadata": {"difficulty": "medium"}},
            {"question_id": 703, "content": "题C", "embedding": [0.3] * 128, "metadata": {"difficulty": "hard"}},
        ]
        count = temp_store.upsert_batch(1, items)
        assert count == 3
        assert temp_store.count(course_id=1) == 3

    def test_get_stats(self, temp_store):
        """全局统计返回 collection 列表。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 801, "题", [0.1] * 128)
        temp_store.upsert(2, 802, "题", [0.2] * 128)
        stats = temp_store.get_stats()
        assert stats["available"] is True
        assert "course_1" in stats["collections"]
        assert "course_2" in stats["collections"]

    def test_clear_course(self, temp_store):
        """清空课程 collection。"""
        if not temp_store.available:
            pytest.skip("ChromaDB 不可用")

        temp_store.upsert(1, 901, "题", [0.1] * 128)
        assert temp_store.count(course_id=1) == 1

        ok = temp_store.clear_course(1)
        assert ok is True
        assert temp_store.count(course_id=1) == 0
