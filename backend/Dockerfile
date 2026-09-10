# 后端服务 Dockerfile（FastAPI + uvicorn，端口 8000）
FROM python:3.11-slim

# 设置 Python 输出无缓冲，日志实时可见
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖：reportlab/openpyxl 需要 libfreetype；编译 chromadb 可能需要 gcc
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝源码
COPY . .

# 数据库与向量数据持久化目录（docker-compose 挂载卷到这里）
# SQLite 默认 ./app.db，ChromaDB 默认 ./chroma_data，均相对 WORKDIR
EXPOSE 8000

# 生产启动：关闭 reload，开 4 worker（SQLite 写锁单线程，worker 数不宜过高）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
