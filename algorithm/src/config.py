"""AI 算法服务配置加载模块。

功能：从环境变量（或 .env 文件）加载 LLM 厂商配置与服务运行参数。
所有配置项集中管理，业务层通过 ``get_settings()`` 获取单例。
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AI 算法服务配置。

    所有字段默认值与 ``.env.example`` 对应，未配置时也可启动（仅在不真正调用 LLM 时）。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- LLM 厂商 ----------
    llm_provider: str = Field(default="qwen", description="LLM 厂商：qwen/deepseek/zhipu/openai")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="OpenAI 兼容端点",
    )
    llm_model: str = Field(default="qwen-plus", description="模型名")

    # ---------- 调用参数 ----------
    llm_timeout: int = Field(default=30, description="单次调用超时（秒）")
    llm_max_retry: int = Field(default=2, description="失败重试次数")
    llm_temperature: float = Field(default=0.7, description="采样温度")
    llm_max_tokens: int = Field(default=4000, description="单次最大输出 token")

    # ---------- 服务运行 ----------
    ai_service_port: int = Field(default=8001, description="服务监听端口")
    ai_cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8000",
        description="允许跨源地址（逗号分隔）",
    )

    @property
    def cors_origins(self) -> list[str]:
        """把逗号分隔的跨源配置解析为列表。"""
        return [o.strip() for o in self.ai_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（进程内缓存，避免重复读 .env）。"""
    return Settings()
