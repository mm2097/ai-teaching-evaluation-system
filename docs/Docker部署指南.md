# Docker 部署指南

AI 教学评价系统三服务一键容器化部署。

## 架构

```
浏览器 ──http://localhost──▶ 前端容器(nginx:80)
                                │ 静态文件 + 反向代理 /api
                                ▼
                          后端容器(fastapi:8000)
                                │ http://algorithm:8001
                                ▼
                          算法服务容器(fastapi:8001)
                                │ HTTPS
                                ▼
                          LLM 厂商(DeepSeek/通义千问)
```

三个容器通过 Docker 自定义网络 `aies-net` 通信，互相用服务名（`backend` / `algorithm`）作为主机名访问。

## 前置条件

- Docker 20.10+（含 Docker Compose v2）
- 一台服务器（2 核 4G 起步）
- LLM API Key（DeepSeek 或通义千问）

## 部署步骤

### 1. 准备环境变量

后端和算法服务各自需要一份 `.env`：

```bash
# 后端配置
cp backend/.env.example backend/.env
# 编辑 backend/.env，至少修改：
#   ENVIRONMENT=production
#   SECRET_KEY=<至少32字符随机值，执行 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成>

# 算法服务配置
cp algorithm/.env.example algorithm/.env
# 编辑 algorithm/.env，至少修改：
#   LLM_API_KEY=<你的 DeepSeek/通义千问 API Key>
#   LLM_PROVIDER / LLM_BASE_URL / LLM_MODEL 按厂商填
```

> 也可以参考根目录 `.env.docker.example`，它把两部分放一起方便对照，部署时拆到对应目录。

### 2. 构建并启动

```bash
docker compose up -d --build
```

首次构建约 5-10 分钟（装 Python 依赖最久）。完成后：

```bash
docker compose ps          # 查看三个容器状态
docker compose logs -f     # 实时查看日志
```

### 3. 访问

浏览器打开 `http://<服务器IP>`（80 端口），即前端页面。

默认管理员账号见 `backend/app/seed.py`（通常 admin/admin）。

### 4. 导入种子数据（可选）

首次部署数据库是空的。导入演示数据：

```bash
# 进后端容器执行种子脚本
docker compose exec backend python -m app.seed --reset
```

> 种子脚本会清空并重建演示数据（课程、学生、题库等）。生产环境慎用 `--reset`。

## 数据持久化

| 数据 | 容器内路径 | Docker 卷 |
|------|-----------|-----------|
| SQLite 主库 | `/app/data/app.db` | `backend-data` |
| ChromaDB 向量库 | `/app/data/chroma_data/` | `backend-data` |

容器重建（`docker compose up --build`）不会丢数据，因为卷是独立的。只有 `docker compose down -v` 才会删除卷。

**备份数据：**

```bash
# 导出 SQLite
docker compose exec backend python -c "import shutil; shutil.copy('data/app.db','/dev/stdout')" > backup_$(date +%F).db
```

## 常用命令

```bash
docker compose up -d --build      # 构建并后台启动
docker compose down               # 停止并删除容器（保留数据）
docker compose down -v            # 停止并删除容器+数据（慎用）
docker compose restart backend    # 重启单个服务
docker compose logs -f backend    # 看后端日志
docker compose ps                 # 查看状态
docker compose exec backend bash  # 进后端容器调试
```

## 配置说明

### 后端环境变量（backend/.env）

| 变量 | 说明 | Docker 默认 |
|------|------|------------|
| `SECRET_KEY` | JWT 密钥，生产必填 ≥32 字符 | 无，必须配置 |
| `ENVIRONMENT` | 运行环境 | compose 设为 `production` |
| `AI_SERVICE_URL` | 算法服务地址 | compose 设为 `http://algorithm:8001` |
| `CORS_ORIGINS` | CORS 允许源，留空=全部 | 空（经 nginx 同源代理） |
| `EMBEDDING_API_KEY` | 向量嵌入 Key，留空回退 TF-IDF | 空 |
| `DATABASE_URL` | SQLite 路径 | compose 设为 `sqlite:///./data/app.db` |

### 算法服务环境变量（algorithm/.env）

| 变量 | 说明 |
|------|------|
| `LLM_PROVIDER` | 厂商：qwen/deepseek/zhipu/openai |
| `LLM_API_KEY` | LLM API Key，必填 |
| `LLM_BASE_URL` | OpenAI 兼容端点 |
| `LLM_MODEL` | 模型名 |

## 故障排查

### 容器起不来

```bash
docker compose logs backend     # 看报错
docker compose logs algorithm
docker compose logs frontend
```

### 后端连不上算法服务

确认两个容器在同一网络：`docker network inspect aies-teaching-evaluation-system_aies-net`。后端调算法服务用 `http://algorithm:8001`（compose 里已配好）。

### 前端页面白屏

```bash
docker compose exec frontend ls /usr/share/nginx/html   # 确认静态文件在
docker compose logs frontend                             # 看 nginx 日志
```

### LLM 调用 503

算法服务日志显示 `LLM_API_KEY 未配置`：检查 `algorithm/.env` 是否正确挂载。

### AI 出题流式接口卡住

nginx 已配置 `proxy_buffering off` 和 300s 超时。若仍卡，检查后端日志是否有超时。

## 与本地开发的区别

| 项 | 本地开发 | Docker |
|----|---------|--------|
| 算法服务地址 | `http://127.0.0.1:8001` | `http://algorithm:8001` |
| 前端访问后端 | Vite proxy `/api`→8000 | nginx proxy `/api`→backend:8000 |
| 数据库路径 | `backend/app.db` | 容器内 `/app/data/app.db`（卷持久化） |
| CORS | localhost:5173/5174 | 默认放开所有源 |

代码层通过 `AI_SERVICE_URL` 和 `CORS_ORIGINS` 两个配置项切换，本地开发默认值不受影响。
