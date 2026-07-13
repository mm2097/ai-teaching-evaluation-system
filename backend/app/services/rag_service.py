"""RAG 检索服务：统一检索入口。

流程：
    1. 向量检索（EmbeddingService + VectorStore）→ Top-K
    2. 按知识点/难度过滤（metadata where 条件）
    3. 向量不可用时回退到 SQL 匹配（原 _retrieve_reference_questions 逻辑）

对外接口：
    - search(course_id, query, top_k, ...) → 向量语义检索
    - retrieve_reference_questions(course_id, knowledge_points, difficulty, top_k) → RAG 参考题（注入 LLM prompt）
    - rebuild_index(session, course_id) → 全量重建向量索引
    - sync_question(session, course_id, question_id, action) → 增量同步单题
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from app.core.embedding import EmbeddingError, get_embedding_service
from app.models import AiQuestion, KnowledgeModule, KnowledgePoint
from app.services.vector_store import get_vector_store

# 题型编号 → 名称
_TYPE_MAP = {1: "single_choice", 2: "multi_choice", 3: "judge", 4: "fill_blank", 5: "short_answer"}


def _difficulty_str(q: AiQuestion) -> str:
    """从 AiQuestion 取难度（有字段就用，无则 medium 兜底）。"""
    return getattr(q, "difficulty", None) or "medium"


class RagService:
    """统一 RAG 检索入口，向量不可用时回退 SQL。"""

    def __init__(self) -> None:
        self._embedding = get_embedding_service()
        self._vector_store = get_vector_store()

    @property
    def vector_available(self) -> bool:
        """向量检索是否可用（API Key + ChromaDB 双就绪）。"""
        return self._embedding.available and self._vector_store.available

    # ===== 核心：向量语义检索 =====

    def search(
        self,
        session: Session,
        course_id: int,
        query: str,
        top_k: int = 5,
        knowledge_points: list[str] | None = None,
        difficulty: str = "",
    ) -> list[dict[str, Any]]:
        """向量语义检索 Top-K 参考题。

        向量不可用 → 回退 SQL 匹配。
        返回: [{question_id, stem, content, options, answer, explanation,
                knowledge_point, difficulty, type, similarity}]
        """
        if not self.vector_available or not query.strip():
            # 回退 SQL
            return self._sql_search(session, course_id, query, top_k, knowledge_points, difficulty)

        try:
            query_vec = self._embedding.embed(query)
        except EmbeddingError as e:
            logger.warning(f"嵌入失败，回退 SQL: {e}")
            return self._sql_search(session, course_id, query, top_k, knowledge_points, difficulty)

        # 构造 where 过滤
        where: dict[str, Any] = {}
        if difficulty:
            where["difficulty"] = difficulty

        results = self._vector_store.search(course_id, query_vec, top_k=top_k * 2, where=where or None)

        if not results:
            # 向量库为空，也回退 SQL
            logger.info(f"课程 {course_id} 向量库无结果，回退 SQL")
            return self._sql_search(session, course_id, query, top_k, knowledge_points, difficulty)

        # 按知识点过滤（向量检索后做）
        question_ids = [r["question_id"] for r in results if isinstance(r["question_id"], int)]
        if not question_ids:
            return self._sql_search(session, course_id, query, top_k, knowledge_points, difficulty)

        q_rows = session.exec(
            select(AiQuestion).where(AiQuestion.question_id.in_(question_ids))  # type: ignore
        ).all()
        q_map = {q.question_id: q for q in q_rows}

        kp_map: dict[int, str] = {}
        for q in q_rows:
            kp = session.get(KnowledgePoint, q.point_id)
            kp_map[q.point_id] = kp.point_name if kp else ""

        # 如果有知识点过滤条件，先做过滤
        kp_filter_set = set(knowledge_points) if knowledge_points else None

        out = []
        for r in results:
            qid = r["question_id"]
            if qid not in q_map:
                continue
            q = q_map[qid]
            kp_name = kp_map.get(q.point_id, "")
            if kp_filter_set and kp_name not in kp_filter_set:
                continue
            out.append(self._format_question(q, kp_name, r["similarity"]))
            if len(out) >= top_k:
                break

        # 向量检索结果不足，用 SQL 补充
        if len(out) < top_k:
            existing_ids = {item["question_id"] for item in out}
            extras = self._sql_search(
                session, course_id, query, top_k - len(out), knowledge_points, difficulty, exclude_ids=existing_ids
            )
            out.extend(extras)

        return out[:top_k]

    # ===== RAG 参考题（注入 LLM prompt 用）=====

    def retrieve_reference_questions(
        self,
        session: Session,
        course_id: int,
        knowledge_points: list[str],
        difficulty: str,
        top_k: int = 5,
    ) -> list[dict[str, str]]:
        """检索参考题用于 RAG 注入 prompt。

        优先向量检索（拼接知识点+难度为 query），回退 SQL。
        返回格式对齐原 _retrieve_reference_questions。
        """
        # 向量可用时，用知识点拼接作为 query 做语义检索
        if self.vector_available and knowledge_points:
            query = " ".join(knowledge_points) + f" {difficulty}"
            vec_results = self.search(
                session, course_id, query, top_k=top_k,
                knowledge_points=knowledge_points, difficulty=difficulty
            )
            if vec_results:
                return [
                    {
                        "type": item["type"],
                        "stem": item["stem"],
                        "options": self._options_to_text(item.get("options")),
                        "answer": item["answer"],
                        "explanation": item.get("explanation", ""),
                        "knowledge_point": item.get("knowledge_point", ""),
                        "difficulty": item.get("difficulty", difficulty),
                        "_question_id": str(item["question_id"]),
                        "_similarity": str(item.get("similarity", 0)),
                    }
                    for item in vec_results
                ]

        # 回退 SQL
        return self._sql_reference_questions(session, course_id, knowledge_points, difficulty, top_k)

    # ===== 索引管理 =====

    def rebuild_index(self, session: Session, course_id: int = 0) -> dict[str, Any]:
        """全量重建向量索引。course_id=0 表示重建所有课程。"""
        if not self.vector_available:
            return {"available": False, "indexed": 0, "error": "向量服务不可用"}

        # 确定要重建的课程列表
        if course_id:
            course_ids = [course_id]
        else:
            from app.models import Course
            course_ids = list(session.exec(select(Course.course_id)).all())

        total_indexed = 0
        for cid in course_ids:
            # 清空旧索引
            self._vector_store.clear_course(cid)
            # 拉所有题目
            questions = session.exec(
                select(AiQuestion).where(AiQuestion.course_id == cid)
            ).all()
            if not questions:
                continue
            # 嵌入
            texts = [self._question_to_text(q) for q in questions]
            try:
                embeddings = self._embedding.embed_batch(texts)
            except EmbeddingError as e:
                logger.error(f"课程 {cid} 批量嵌入失败: {e}")
                continue

            items = []
            for q, emb in zip(questions, embeddings):
                kp = session.get(KnowledgePoint, q.point_id)
                items.append({
                    "question_id": q.question_id,
                    "content": q.content,
                    "embedding": emb,
                    "metadata": {
                        "knowledge_point": kp.point_name if kp else "",
                        "difficulty": _difficulty_str(q),
                        "type": _TYPE_MAP.get(q.type, "unknown"),
                        "course_id": cid,
                    },
                })
            count = self._vector_store.upsert_batch(cid, items)
            total_indexed += count
            logger.info(f"课程 {cid} 索引重建: {count} 题")

        return {"available": True, "indexed": total_indexed, "courses": len(course_ids)}

    def sync_question(
        self, session: Session, course_id: int, question_id: int, action: str = "upsert"
    ) -> bool:
        """增量同步单道题到向量索引。action: upsert / delete。"""
        if not self.vector_available:
            return False

        if action == "delete":
            return self._vector_store.delete(course_id, question_id)

        # upsert
        q = session.get(AiQuestion, question_id)
        if not q:
            return self._vector_store.delete(course_id, question_id)

        try:
            embedding = self._embedding.embed(self._question_to_text(q))
        except EmbeddingError as e:
            logger.warning(f"同步题目 {question_id} 嵌入失败: {e}")
            return False

        kp = session.get(KnowledgePoint, q.point_id)
        metadata = {
            "knowledge_point": kp.point_name if kp else "",
            "difficulty": _difficulty_str(q),
            "type": _TYPE_MAP.get(q.type, "unknown"),
            "course_id": course_id,
        }
        return self._vector_store.upsert(course_id, question_id, q.content, embedding, metadata)

    def init_if_empty(self, session: Session) -> dict[str, Any]:
        """索引为空时触发全量同步（lifespan 调用）。"""
        if not self.vector_available:
            return {"available": False, "indexed": 0}
        stats = self._vector_store.get_stats()
        total = sum(stats.get("collections", {}).values())
        if total == 0:
            logger.info("向量索引为空，触发全量同步...")
            return self.rebuild_index(session)
        return {"available": True, "indexed": 0, "skipped": "索引非空"}

    # ===== 内部方法 =====

    def _question_to_text(self, q: AiQuestion) -> str:
        """把题目拼成可嵌入的文本。"""
        parts = [q.content]
        if q.options:
            try:
                opts = json.loads(q.options)
                if isinstance(opts, list):
                    parts.append(" ".join(str(o) for o in opts))
            except (ValueError, TypeError):
                parts.append(q.options)
        if q.correct_answer:
            parts.append(q.correct_answer)
        return " ".join(parts)

    def _format_question(self, q: AiQuestion, kp_name: str, similarity: float) -> dict[str, Any]:
        """AiQuestion → 返回 dict（含 similarity）。"""
        options = []
        if q.options:
            try:
                options = json.loads(q.options)
            except (ValueError, TypeError):
                options = []
        return {
            "question_id": q.question_id,
            "stem": q.content,
            "content": q.content,
            "options": options,
            "answer": q.correct_answer,
            "explanation": q.analysis or "",
            "knowledge_point": kp_name,
            "difficulty": _difficulty_str(q),
            "type": _TYPE_MAP.get(q.type, "single_choice"),
            "similarity": similarity,
        }

    def _options_to_text(self, options: list | str) -> str:
        """选项列表 → 文本。"""
        if isinstance(options, str):
            return options
        if isinstance(options, list):
            return "；".join(str(o) for o in options)
        return ""

    def _sql_search(
        self,
        session: Session,
        course_id: int,
        query: str,
        top_k: int,
        knowledge_points: list[str] | None,
        difficulty: str,
        exclude_ids: set[int] | None = None,
    ) -> list[dict[str, Any]]:
        """SQL 回退检索（复用原 _retrieve_reference_questions 逻辑 + TF-IDF）。"""
        from app.services.dedup import _build_tfidf, _cosine, _tokenize

        # 按知识点找 point_id
        point_ids: list[int] = []
        if knowledge_points:
            kps = session.exec(
                select(KnowledgePoint)
                .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
                .where(
                    KnowledgeModule.course_id == course_id,
                    KnowledgePoint.point_name.in_(knowledge_points),  # type: ignore
                )
            ).all()
            point_ids = [kp.point_id for kp in kps]

        # 查候选题
        stmt = (
            select(AiQuestion, KnowledgePoint)
            .join(KnowledgePoint, AiQuestion.point_id == KnowledgePoint.point_id)
            .where(AiQuestion.course_id == course_id)
        )
        if point_ids:
            stmt = stmt.where(AiQuestion.point_id.in_(point_ids))  # type: ignore
        if difficulty:
            stmt = stmt.where(AiQuestion.difficulty == difficulty)
        if exclude_ids:
            stmt = stmt.where(~AiQuestion.question_id.in_(exclude_ids))  # type: ignore

        rows = session.exec(stmt).all()
        if not rows:
            return []

        # TF-IDF 语义匹配
        q_dicts = []
        for q, kp in rows:
            q_dicts.append(self._format_question(q, kp.point_name, 0.0))

        if query.strip():
            docs = [_tokenize(query)]
            for qd in q_dicts:
                text = qd["content"]
                if qd.get("options"):
                    text += " " + " ".join(str(o) for o in qd["options"])
                docs.append(_tokenize(text))
            vecs = _build_tfidf(docs)
            query_vec = vecs[0]
            for i, qd in enumerate(q_dicts):
                qd["similarity"] = round(_cosine(query_vec, vecs[i + 1]), 4)
            q_dicts.sort(key=lambda x: x["similarity"], reverse=True)

        return q_dicts[:top_k]

    def _sql_reference_questions(
        self,
        session: Session,
        course_id: int,
        knowledge_points: list[str],
        difficulty: str,
        top_k: int,
    ) -> list[dict[str, str]]:
        """SQL 回退参考题（对齐原 _retrieve_reference_questions 格式）。"""
        point_ids: list[int] = []
        if knowledge_points:
            kps = session.exec(
                select(KnowledgePoint)
                .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
                .where(
                    KnowledgeModule.course_id == course_id,
                    KnowledgePoint.point_name.in_(knowledge_points),  # type: ignore
                )
            ).all()
            point_ids = [kp.point_id for kp in kps]

        matched: list[AiQuestion] = []
        if point_ids:
            matched = list(session.exec(
                select(AiQuestion).where(
                    AiQuestion.course_id == course_id,
                    AiQuestion.point_id.in_(point_ids),  # type: ignore
                    AiQuestion.difficulty == difficulty,
                ).limit(top_k)
            ).all())

        # 不足时跨知识点补充
        if len(matched) < top_k:
            existing_ids = {q.question_id for q in matched}
            extra = list(session.exec(
                select(AiQuestion).where(
                    AiQuestion.course_id == course_id,
                    AiQuestion.difficulty == difficulty,
                    ~AiQuestion.question_id.in_(existing_ids) if existing_ids else True,  # type: ignore
                ).limit(top_k - len(matched))
            ).all())
            matched.extend(extra)

        result = []
        for q in matched[:top_k]:
            kp = session.get(KnowledgePoint, q.point_id)
            options_text = ""
            if q.options:
                try:
                    opts = json.loads(q.options)
                    options_text = "；".join(opts) if isinstance(opts, list) else str(opts)
                except (ValueError, TypeError):
                    options_text = q.options or ""
            result.append({
                "type": _TYPE_MAP.get(q.type, "single_choice"),
                "stem": q.content,
                "options": options_text,
                "answer": q.correct_answer,
                "explanation": q.analysis or "",
                "knowledge_point": kp.point_name if kp else "",
                "difficulty": _difficulty_str(q),
            })
        return result


# ===== 模块级单例 =====

_rag_service: RagService | None = None


def get_rag_service() -> RagService:
    """获取全局 RagService 单例。"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService()
    return _rag_service


def reset_rag_service() -> None:
    """重置单例（测试用）。"""
    global _rag_service
    _rag_service = None
