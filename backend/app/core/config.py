from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置,从 .env 或环境变量读取,所有项均有默认值。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "AI 教学评价系统"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite:///./app.db"
    LOG_LEVEL: str = "INFO"
    # JWT
    SECRET_KEY: str = "dev-secret-change-in-production"  # 生产环境务必改成随机长串
    TOKEN_EXPIRE_HOURS: int = 24 * 7  # token 有效期 7 天

    # ===== 向量嵌入（RAG 升级） =====
    EMBEDDING_API_KEY: str = ""  # Silicon Flow / Dashscope 等 OpenAI 兼容 Key
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DIM: int = 1024
    CHROMA_PERSIST_PATH: str = "./chroma_data"  # ChromaDB 持久化目录


settings = Settings()
