import sys

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """配置 loguru:控制台彩色输出 + 文件轮转(10MB 切分,保留 7 天,zip 压缩)。"""
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, level=settings.LOG_LEVEL, format=fmt, enqueue=True)
    logger.add(
        "logs/app.log",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )
