"""EmbeddingService 单元测试。

mock httpx，验证：
- 请求格式（Authorization / model / input）
- 批量分批
- 错误处理（HTTP 错误、网络不可达、返回数量不匹配）
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

import httpx

from app.core.embedding import EmbeddingService, EmbeddingError


class TestEmbeddingService:
    """EmbeddingService 核心测试。"""

    def test_available_with_key(self):
        """配置了 API Key 时 available=True。"""
        svc = EmbeddingService(api_key="sk-test")
        assert svc.available is True

    def test_not_available_without_key(self):
        """未配置 API Key 时 available=False。"""
        svc = EmbeddingService(api_key="")
        assert svc.available is False

    def test_embed_without_key_raises(self):
        """无 Key 时 embed 抛异常。"""
        svc = EmbeddingService(api_key="")
        with pytest.raises(EmbeddingError, match="未配置"):
            svc.embed("test")

    def test_embed_batch_without_key_raises(self):
        """无 Key 时 embed_batch 抛异常。"""
        svc = EmbeddingService(api_key="")
        with pytest.raises(EmbeddingError):
            svc.embed_batch(["a", "b"])

    def test_embed_batch_empty(self):
        """空列表返回空。"""
        svc = EmbeddingService(api_key="sk-test")
        assert svc.embed_batch([]) == []

    @patch("app.core.embedding.httpx.post")
    def test_single_embed_request_format(self, mock_post):
        """验证请求格式：URL / headers / payload。"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "bge-large-zh",
            "usage": {"prompt_tokens": 5},
        }
        mock_post.return_value = mock_resp

        svc = EmbeddingService(
            api_key="sk-test", base_url="https://api.test.com/v1",
            model="bge-zh", dim=3,
        )
        vec = svc.embed("你好")

        assert vec == [0.1, 0.2, 0.3]
        # 验证请求参数
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
        assert url == "https://api.test.com/v1/embeddings"
        payload = call_kwargs.kwargs.get("json", {})
        assert payload["model"] == "bge-zh"
        assert payload["input"] == ["你好"]
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer sk-test"

    @patch("app.core.embedding.httpx.post")
    def test_batch_embed_batching(self, mock_post):
        """批量分批：batch_size=2，3 条文本应分 2 批。"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.side_effect = [
            {"data": [
                {"embedding": [1.0, 0.0], "index": 0},
                {"embedding": [0.0, 1.0], "index": 1},
            ]},
            {"data": [{"embedding": [0.5, 0.5], "index": 0}]},
        ]
        mock_post.return_value = mock_resp

        svc = EmbeddingService(api_key="sk-test", dim=2, batch_size=2)
        results = svc.embed_batch(["a", "b", "c"])

        assert len(results) == 3
        assert results[0] == [1.0, 0.0]
        assert results[1] == [0.0, 1.0]
        assert results[2] == [0.5, 0.5]
        # 应调用 2 次
        assert mock_post.call_count == 2

    @patch("app.core.embedding.httpx.post")
    def test_http_error_raises(self, mock_post):
        """HTTP 4xx 错误应抛 EmbeddingError。"""
        err_resp = MagicMock()
        err_resp.status_code = 401
        err_resp.text = "Unauthorized"
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=err_resp,
        )
        mock_post.return_value = err_resp

        svc = EmbeddingService(api_key="sk-bad")
        with pytest.raises(EmbeddingError):
            svc.embed("test")

    @patch("app.core.embedding.httpx.post")
    def test_connect_error_raises(self, mock_post):
        """网络不可达应抛 EmbeddingError。"""
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        svc = EmbeddingService(api_key="sk-test")
        with pytest.raises(EmbeddingError):
            svc.embed("test")

    @patch("app.core.embedding.httpx.post")
    def test_count_mismatch_raises(self, mock_post):
        """返回嵌入数量与请求不匹配应抛异常。"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1], "index": 0}],  # 请求 2 条但只返回 1 条
        }
        mock_post.return_value = mock_resp

        svc = EmbeddingService(api_key="sk-test", dim=1)
        with pytest.raises(EmbeddingError, match="不匹配"):
            svc.embed_batch(["a", "b"])

    @patch("app.core.embedding.httpx.post")
    def test_result_order_by_index(self, mock_post):
        """结果按 index 排序（即使返回顺序乱）。"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "data": [
                {"embedding": [0.0, 2.0], "index": 1},
                {"embedding": [1.0, 0.0], "index": 0},
            ],
        }
        mock_post.return_value = mock_resp

        svc = EmbeddingService(api_key="sk-test", dim=2)
        results = svc.embed_batch(["first", "second"])
        # index=0 在前
        assert results[0] == [1.0, 0.0]
        assert results[1] == [0.0, 2.0]

    def test_text_hash(self):
        """文本哈希稳定。"""
        svc = EmbeddingService(api_key="sk-test")
        h1 = svc.text_hash("hello")
        h2 = svc.text_hash("hello")
        h3 = svc.text_hash("world")
        assert h1 == h2
        assert h1 != h3
