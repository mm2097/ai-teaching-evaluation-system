"""LLM 客户端封装。

功能：统一封装通义千问（OpenAI 兼容模式）的调用，支持：
- JSON 模式输出
- 超时与重试
- token 与耗时记录
- 多厂商可切（qwen/deepseek/zhipu/openai，仅需改环境变量）

业务层只调 ``LLMClient.chat_completion()``，不感知具体厂商。
"""
from dataclasses import dataclass

from loguru import logger
from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from .config import get_settings


@dataclass
class LLMResult:
    """LLM 调用结果。"""

    content: str          # 模型原始输出文本
    model: str            # 实际使用的模型名
    input_tokens: int     # 输入 token 数
    output_tokens: int    # 输出 token 数
    retry_count: int      # 实际重试次数


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
        """调用 LLM 完成一次对话。

        参数：
            system_prompt: 系统指令
            user_prompt: 用户指令
            json_mode: 是否启用 JSON 模式（默认 True，出题必需）

        返回：``LLMResult``，包含输出文本与 token/重试统计

        异常：所有重试耗尽后抛 ``RuntimeError``，由调用方捕获转 503。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # JSON 模式：要求厂商支持 response_format（通义/DeepSeek/OpenAI 均支持）
        response_format = {"type": "json_object"} if json_mode else None

        last_error: Exception | None = None
        for attempt in range(self._max_retry + 1):
            try:
                logger.info(
                    f"LLM 调用 第 {attempt + 1}/{self._max_retry + 1} 次 model={self._model}"
                )
                kwargs: dict = dict(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
                if response_format:
                    kwargs["response_format"] = response_format

                resp = self._client.chat.completions.create(**kwargs)

                content = resp.choices[0].message.content or ""
                usage = resp.usage
                return LLMResult(
                    content=content,
                    model=self._model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    retry_count=attempt,
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

        # 全部重试失败
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
