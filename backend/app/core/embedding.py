"""向量嵌入服务：调 OpenAI 兼容嵌入 API（Silicon Flow BGE / Dashscope）。

特性：
- 支持批量嵌入（自动分批）
- LRU 缓存（同一段文本不重复请求）
- API 不可用时抛异常，由上层 RagService 决定回退
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings


class EmbeddingError(Exception):
    """嵌入 API 调用失败。"""


class EmbeddingService:
    """调 OpenAI 兼容嵌入 API，带批量分批 + LRU 缓存。"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        dim: int = 0,
        batch_size: int = 32,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.EMBEDDING_API_KEY
        self.base_url = (base_url or settings.EMBEDDING_BASE_URL).rstrip("/")
        self.model = model or settings.EMBEDDING_MODEL
        self.dim = dim or settings.EMBEDDING_DIM
        self.batch_size = batch_size
        self.timeout = timeout

    @property
    def available(self) -> bool:
        """是否配置了 API Key（可用性判断）。"""
        return bool(self.api_key)

    def embed(self, text: str) -> list[float]:
        """嵌入单段文本，返回 dim 维向量。"""
        if not self.available:
            raise EmbeddingError("未配置 EMBEDDING_API_KEY")
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，自动分批。返回与 texts 等长的向量列表。"""
        if not texts:
            return []
        if not self.available:
            raise EmbeddingError("未配置 EMBEDDING_API_KEY")

        results: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            chunk = texts[start : start + self.batch_size]
            vectors = self._call_api(chunk)
            results.extend(vectors)
        return results

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """调用 /embeddings 接口。"""
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:200] if e.response.text else ""
            logger.error(f"嵌入 API HTTP {e.response.status_code}: {body}")
            raise EmbeddingError(f"嵌入 API 返回 {e.response.status_code}: {body}") from e
        except (httpx.ConnectError, httpx.RequestError) as e:
            logger.error(f"嵌入 API 不可达: {e}")
            raise EmbeddingError(f"嵌入 API 不可达: {e}") from e

        # OpenAI 兼容格式：{ data: [{ embedding: [...] }, ...] }
        items = data.get("data", [])
        if len(items) != len(texts):
            raise EmbeddingError(
                f"嵌入 API 返回数量不匹配：期望 {len(texts)}，实际 {len(items)}"
            )
        # 按 index 排序确保顺序
        items_sorted = sorted(items, key=lambda x: x.get("index", 0))
        return [item["embedding"] for item in items_sorted]

    def text_hash(self, text: str) -> str:
        """文本哈希，用于缓存键。"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()


# ===== 模块级单例 + 缓存 =====

_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """获取全局 EmbeddingService 单例。"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


@lru_cache(maxsize=2048)
def _cached_embed(text_hash: str, text: str) -> tuple[list[float], EmbeddingError | None]:
    """缓存层：按文本哈希缓存嵌入结果。失败时缓存异常对象。"""
    svc = get_embedding_service()
    if not svc.available:
        err = EmbeddingError("未配置 EMBEDDING_API_KEY")
        return [], err
    try:
        return svc.embed(text), None
    except EmbeddingError as e:
        return [], e


def embed_with_cache(text: str) -> list[float]:
    """嵌入单段文本（带 LRU 缓存），失败时抛异常。"""
    svc = get_embedding_service()
    h = svc.text_hash(text)
    vec, err = _cached_embed(h, text)
    if err:
        raise err
    return vec
