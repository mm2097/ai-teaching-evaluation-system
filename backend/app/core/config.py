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


settings = Settings()
