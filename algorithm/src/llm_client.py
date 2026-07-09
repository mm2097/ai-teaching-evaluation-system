"""LLM 客户端封装。

功能：统一封装通义千问（OpenAI 兼容模式）的调用，支持：
- JSON 模式输出
- Function Calling（tools / tool_calls）
- 超时与重试
- token 与耗时记录
- 多厂商可切（qwen/deepseek/zhipu/openai，仅需改环境变量）

业务层只调 ``LLMClient.chat_completion()`` 或 ``chat_with_tools()``，不感知具体厂商。
"""
from dataclasses import dataclass, field

from loguru import logger
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from .config import get_settings


@dataclass
class LLMResult:
    """LLM 调用结果。"""

    content: str          # 模型原始输出文本（tool_calls 时可能为空）
    model: str            # 实际使用的模型名
    input_tokens: int     # 输入 token 数
    output_tokens: int    # 输出 token 数
    retry_count: int      # 实际重试次数
    tool_calls: list[dict] = field(default_factory=list)
    # tool_calls 结构：[{name, arguments(dict), id}]；无工具调用时为空
    finish_reason: str = "stop"  # stop / tool_calls / length


class LLMClient:
    """LLM 客户端单例。

    基于官方 ``openai`` SDK，通过 ``base_url`` + ``api_key`` 切换不同厂商。
    """

    def __init__(self) -> None:
        s = get_settings()
        if not s.llm_api_key:
            logger.warning("LLM_API_KEY 未配置，LLM 调用将失败；请在 .env 中设置")
        self._client = OpenAI(
            api_key=s.llm_api_key or "missing",
            base_url=s.llm_base_url,
            timeout=s.llm_timeout,
        )
        self._model = s.llm_model
        self._temperature = s.llm_temperature
        self._max_tokens = s.llm_max_tokens
        self._max_retry = s.llm_max_retry

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True,
    ) -> LLMResult:
        """调用 LLM 完成一次对话（无工具调用版，出题等场景使用）。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call(messages, json_mode=json_mode)

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        json_mode: bool = False,
        tool_choice: str = "auto",
    ) -> LLMResult:
        """Function Calling 主入口（Agent 用）。

        参数：
            messages: 完整对话历史（含 system / user / assistant / tool）
            tools: OpenAI Function Calling schema
                    [{type:"function", function:{name, description, parameters}}]
            json_mode: 是否同时强制 JSON 输出（默认 False，Agent 场景通常不强制）
            tool_choice: "auto" / "none" / {"type":"function","function":{"name":...}}

        返回：``LLMResult``。若模型决定调用工具，``tool_calls`` 非空，
              ``content`` 可能为空；否则 ``content`` 为最终回答。

        异常：重试耗尽抛 ``RuntimeError``。
        """
        return self._call(
            messages=messages,
            json_mode=json_mode,
            tools=tools,
            tool_choice=tool_choice if tools else None,
        )

    def _call(
        self,
        messages: list[dict],
        json_mode: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> LLMResult:
        """统一调用内核（chat_completion 与 chat_with_tools 共用）。"""
        response_format = {"type": "json_object"} if json_mode else None

        last_error: Exception | None = None
        for attempt in range(self._max_retry + 1):
            try:
                logger.info(
                    f"LLM 调用 第 {attempt + 1}/{self._max_retry + 1} 次 "
                    f"model={self._model} tools={'on' if tools else 'off'}"
                )
                kwargs: dict = dict(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                if response_format and not tools:
                    # 工具调用时不强制 JSON（部分厂商互斥）
                    kwargs["response_format"] = response_format
                if tools:
                    kwargs["tools"] = tools
                    if tool_choice:
                        kwargs["tool_choice"] = tool_choice

                resp = self._client.chat.completions.create(**kwargs)
                msg = resp.choices[0].message
                finish = resp.choices[0].finish_reason or "stop"
                content = msg.content or ""
                usage = resp.usage

                tool_calls: list[dict] = []
                if getattr(msg, "tool_calls", None):
                    import json as _json
                    for tc in msg.tool_calls:
                        try:
                            args = _json.loads(tc.function.arguments or "{}")
                        except (ValueError, TypeError):
                            args = {"_raw": tc.function.arguments}
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": args,
                        })

                return LLMResult(
                    content=content,
                    model=self._model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    retry_count=attempt,
                    tool_calls=tool_calls,
                    finish_reason=finish,
                )

            except APITimeoutError as e:
                last_error = e
                logger.warning(f"LLM 超时（第 {attempt + 1} 次）: {e}")
            except RateLimitError as e:
                last_error = e
                logger.warning(f"LLM 限流（第 {attempt + 1} 次）: {e}")
            except APIError as e:
                last_error = e
                logger.warning(f"LLM API 错误（第 {attempt + 1} 次）: {e}")

        raise RuntimeError(
            f"LLM 调用失败，已重试 {self._max_retry} 次：{last_error}"
        )


# ===== 单例 =====
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例。"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
