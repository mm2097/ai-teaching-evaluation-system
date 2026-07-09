"""LLM 网关代理：通过 HTTP 调 algorithm 服务的 /agent/chat 接口。

抽象接口 LLMProxy，可被测试用 MockLLMProxy 替换。
默认实现 HTTPProxyLLMProxy 走 httpx 调 8001。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from loguru import logger


@dataclass
class FCResult:
    """单步 FC 调用结果（对应 algorithm/src/llm_client.LLMResult）。"""

    content: str
    tool_calls: list[dict]        # [{id, name, arguments}]
    finish_reason: str = "stop"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProxy(ABC):
    """LLM 网关抽象接口。"""

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> FCResult:
        ...


class HTTPProxyLLMProxy(LLMProxy):
    """走 HTTP 调 algorithm 8001。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8001", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> FCResult:
        import httpx
        url = f"{self.base_url}/agent/chat"
        try:
            resp = httpx.post(
                url,
                json={"messages": messages, "tools": tools, "tool_choice": tool_choice},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return FCResult(
                content=data.get("content", ""),
                tool_calls=data.get("tool_calls", []),
                finish_reason=data.get("finish_reason", "stop"),
                model=data.get("model", ""),
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM 网关 HTTP {e.response.status_code}：{e.response.text[:200]}")
            raise RuntimeError(f"LLM 网关错误 {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"LLM 网关请求失败：{e}")
            raise RuntimeError(f"LLM 网关不可达：{e}")


class MockLLMProxy(LLMProxy):
    """测试用 Mock：按预设脚本返回。"""

    def __init__(self, script: list[FCResult]) -> None:
        """script 是一个结果序列，每次调用消费一条。"""
        self._script = list(script)
        self._idx = 0

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> FCResult:
        if self._idx >= len(self._script):
            return FCResult(content="（Mock 脚本耗尽，返回默认）", tool_calls=[])
        r = self._script[self._idx]
        self._idx += 1
        return r


# 单例
_proxy: LLMProxy | None = None


def get_llm_proxy() -> LLMProxy:
    global _proxy
    if _proxy is None:
        _proxy = HTTPProxyLLMProxy()
    return _proxy


def set_llm_proxy(proxy: LLMProxy) -> None:
    """测试注入用。"""
    global _proxy
    _proxy = proxy
