"""向量存储：ChromaDB 封装。

按课程分 collection，管 upsert / delete / search / rebuild。
ChromaDB 不可用时（如 chromadb 未安装），上层 RagService 回退到 SQL 匹配。
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.config import settings

# ChromaDB 可选依赖：未安装时降级
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


def _collection_name(course_id: int) -> str:
    """课程 → collection 名。"""
    return f"course_{course_id}"


class VectorStore:
    """ChromaDB 封装，按课程隔离 collection。"""

    def __init__(self, persist_path: str = "", dim: int = 0) -> None:
        self.persist_path = persist_path or settings.CHROMA_PERSIST_PATH
        self.dim = dim or settings.EMBEDDING_DIM
        self._client = None
        self._collections: dict[str, Any] = {}

        if not _CHROMA_AVAILABLE:
            logger.warning("chromadb 未安装，VectorStore 不可用，RAG 将回退 SQL 匹配")
            return

        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_path,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
            )
            logger.info(f"ChromaDB 初始化成功: {self.persist_path}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"ChromaDB 初始化失败: {e}")
            self._client = None

    @property
    def available(self) -> bool:
        """ChromaDB 是否可用。"""
        return _CHROMA_AVAILABLE and self._client is not None

    def _get_collection(self, course_id: int):
        """获取或创建课程的 collection。"""
        if not self.available:
            return None
        name = _collection_name(course_id)
        if name not in self._collections:
            try:
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"获取 collection {name} 失败: {e}")
                return None
        return self._collections[name]

    def upsert(
        self,
        course_id: int,
        question_id: int,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """向课程 collection 插入/更新一道题的向量。"""
        col = self._get_collection(course_id)
        if col is None:
            return False
        # ChromaDB 要求 metadata 非空
        meta = metadata if metadata else {"_default": 1}
        try:
            col.upsert(
                ids=[str(question_id)],
                embeddings=[embedding],
                documents=[content],
                metadatas=[meta],
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"upsert 题目 {question_id} 到课程 {course_id} 失败: {e}")
            return False

    def upsert_batch(
        self,
        course_id: int,
        items: list[dict[str, Any]],
    ) -> int:
        """批量插入/更新。items: [{question_id, content, embedding, metadata}]。"""
        col = self._get_collection(course_id)
        if col is None or not items:
            return 0
        # 确保 metadata 非空
        metas = []
        for it in items:
            m = it.get("metadata", {})
            metas.append(m if m else {"_default": 1})
        try:
            col.upsert(
                ids=[str(it["question_id"]) for it in items],
                embeddings=[it["embedding"] for it in items],
                documents=[it["content"] for it in items],
                metadatas=metas,
            )
            return len(items)
        except Exception as e:  # noqa: BLE001
            logger.error(f"批量 upsert 课程 {course_id} 失败: {e}")
            return 0

    def delete(self, course_id: int, question_id: int) -> bool:
        """从课程 collection 删除一道题。"""
        col = self._get_collection(course_id)
        if col is None:
            return False
        try:
            col.delete(ids=[str(question_id)])
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"删除题目 {question_id} 失败: {e}")
            return False

    def search(
        self,
        course_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """向量检索 Top-K。

        返回 [{id, content, metadata, similarity}]
        similarity = 1 - distance（ChromaDB cosine distance）
        """
        col = self._get_collection(course_id)
        if col is None:
            return []
        try:
            kwargs: dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
            }
            if where:
                kwargs["where"] = where
            result = col.query(**kwargs)
        except Exception as e:  # noqa: BLE001
            logger.error(f"向量检索课程 {course_id} 失败: {e}")
            return []

        ids_list = result.get("ids", [[]])
        docs_list = result.get("documents", [[]])
        metas_list = result.get("metadatas", [[]])
        dists_list = result.get("distances", [[]])

        if not ids_list or not ids_list[0]:
            return []

        out = []
        for idx, qid in enumerate(ids_list[0]):
            distance = dists_list[0][idx] if idx < len(dists_list[0]) else 1.0
            similarity = max(0.0, 1.0 - distance)  # cosine distance → similarity
            out.append({
                "question_id": int(qid) if str(qid).lstrip("-").isdigit() else qid,
                "content": docs_list[0][idx] if idx < len(docs_list[0]) else "",
                "metadata": metas_list[0][idx] if idx < len(metas_list[0]) else {},
                "similarity": round(similarity, 4),
            })
        return out

    def count(self, course_id: int) -> int:
        """返回课程 collection 中的题目数。"""
        col = self._get_collection(course_id)
        if col is None:
            return 0
        try:
            return col.count()
        except Exception:  # noqa: BLE001
            return 0

    def get_stats(self) -> dict[str, Any]:
        """全局统计：各 collection 的题目数。"""
        if not self.available:
            return {"available": False, "collections": {}}
        stats: dict[str, int] = {}
        try:
            collections = self._client.list_collections()
            for col in collections:
                stats[col.name] = col.count()
        except Exception as e:  # noqa: BLE001
            logger.error(f"获取 ChromaDB 统计失败: {e}")
        return {"available": True, "collections": stats}

    def clear_course(self, course_id: int) -> bool:
        """清空课程 collection（用于全量重建）。"""
        if not self.available:
            return False
        name = _collection_name(course_id)
        try:
            self._client.delete_collection(name)
            self._collections.pop(name, None)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"清空 collection {name} 失败: {e}")
            return False


# ===== 模块级单例 =====

_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """获取全局 VectorStore 单例。"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reset_vector_store() -> None:
    """重置单例（测试用）。"""
    global _vector_store
    _vector_store = None
