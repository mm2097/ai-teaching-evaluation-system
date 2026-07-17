import secrets
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """应用配置,从 .env 或环境变量读取,所有项均有默认值。"""

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_DIR / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "AI 教学评价系统"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite:///./app.db"
    LOG_LEVEL: str = "INFO"
    # JWT
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    SECRET_KEY: str = ""
    TOKEN_EXPIRE_HOURS: int = 24 * 7  # token 有效期 7 天
    # AI 出题配额
    AI_STUDENT_DAILY_REQUEST_LIMIT: int = Field(default=5, ge=1, le=100)
    AI_STUDENT_MAX_QUESTIONS: int = Field(default=10, ge=1, le=30)
    AI_STAFF_DAILY_REQUEST_LIMIT: int = Field(default=30, ge=1, le=1000)
    AI_SERVICE_PORT: int = Field(default=8001, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """生产环境必须显式配置强密钥；开发/测试环境缺省使用固定密钥，避免重启后全员掉线。"""
        if self.ENVIRONMENT == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("生产环境必须配置至少 32 字符的 SECRET_KEY")
        if not self.SECRET_KEY:
            if self.ENVIRONMENT in {"development", "test"}:
                self.SECRET_KEY = "dev-teaching-eval-secret-key-do-not-use-in-prod"
            else:
                self.SECRET_KEY = secrets.token_urlsafe(48)
        return self

    # ===== 向量嵌入（RAG 升级） =====
    EMBEDDING_API_KEY: str = ""  # Silicon Flow / Dashscope 等 OpenAI 兼容 Key
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DIM: int = 1024
    CHROMA_PERSIST_PATH: str = "./chroma_data"  # ChromaDB 持久化目录


settings = Settings()
