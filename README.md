# AI 辅助教学评价系统

monorepo:前端(Vue 3)+ 后端(FastAPI)+ 算法(Python)。

## 目录结构

```
ai-teaching-evaluation-system/
├── docs/          # 会议记录、周计划、模板
├── frontend/      # Vue 3 + TS + Vite + Element Plus + Pinia + ECharts
├── backend/       # FastAPI + SQLModel + loguru
└── algorithm/     # 算法侧(Python,占位)
```

## 环境要求

- **Node.js** `^22.18.0 || >=24.12.0`(前端)
- **Python** `>=3.10`(后端、算法)
- 任意一个数据库:默认 SQLite(零配置),需要时可换 PostgreSQL

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

其他脚本:

```bash
npm run build       # 生产构建
npm run type-check  # TS 类型检查
npm run lint        # oxlint + eslint 修复
npm run format      # prettier 格式化 src/
```

## 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Swagger(交互式接口文档):http://127.0.0.1:8000/docs
- ReDoc(只读文档):http://127.0.0.1:8000/redoc
- 健康检查:http://127.0.0.1:8000/api/health → `{"status":"ok"}`
- 日志文件:`backend/logs/app.log`(10MB 轮转,保留 7 天)
- 数据库文件:`backend/app.db`(首次启动自动生成)

### 配置

默认值开箱即用。如需修改,在 `backend/` 下复制 `.env.example` 为 `.env`:

```bash
cp .env.example .env
```

常用项:`DATABASE_URL`(切换数据库)、`LOG_LEVEL`(日志级别)。

### 后端目录约定(给后续接手同学)

| 想做的事 | 在哪里 |
|----------|--------|
| 加接口 | `app/api/v1/` 下建文件,定义 `router`,在 `main.py` 里 `include_router` |
| 加数据表 | `app/models/` 下建文件定义 `SQLModel`,在 `models/__init__.py` 里 import,重启自动建表 |
| 改配置 | `app/core/config.py`(或 `.env`) |
| 加中间件 | `app/main.py` |

## 算法侧

占位,待后续补充依赖与模型。

## 协作

- 主分支:`main`,开发分支:`dev`
- 详细任务分工与会议记录见 `docs/`
