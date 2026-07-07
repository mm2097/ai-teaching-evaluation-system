# AI 辅助教学评价系统

基于数据分析与 AI 的教学评价平台,monorepo 管理:前端(Vue 3)+ 后端(FastAPI)+ 算法(Python)。

## 项目介绍

本系统面向教学过程的多维度评价,主要功能模块:

- **数据管理**:成绩/评教数据导入、清洗、统一管理
- **智能分析**:成绩趋势、学生画像、知识点掌握、相关性分析、学情预警
- **教学评价**:课程评价、学生评价、教师评价、评价配置
- **报告中心**:生成与导出评价报告
- **系统管理**:用户管理、日志、参数配置

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3.5 + TypeScript + Vite + Element Plus + Pinia + Vue Router + ECharts + Axios |
| 后端 | FastAPI + SQLModel + loguru + SQLite(可平滑切换 PostgreSQL) |
| 算法 | Python(占位,待补充) |

## 目录结构

```
ai-teaching-evaluation-system/
├── docs/          # 会议记录、周计划、模板
├── frontend/      # 前端(Vue 3)
├── backend/       # 后端(FastAPI)
│   └── app/
│       ├── api/v1/    # 接口路由
│       ├── core/      # 配置、日志、数据库
│       ├── models/    # 数据模型(SQLModel)
│       └── seed.py    # 演示数据脚本
└── algorithm/     # 算法侧(Python,占位)
```

## 环境准备(需要装什么)

### 必装

| 软件 | 版本 | 用于 | 下载 |
|------|------|------|------|
| **Node.js** | `^22.18.0 \|\| >=24.12.0` | 前端 | https://nodejs.org |
| **Python** | `>=3.10` | 后端、算法 | https://www.python.org |

> 安装后在项目根目录分别验证:`node -v`、`python --version`(Windows 若是 `python3` 自行替换)。

### 不需要装

- ❌ **数据库服务器**:用 SQLite,它是 Python 标准库自带的(`sqlite3` 模块),装好 Python 就有了,**不用单独安装、不用启动服务**。数据存在一个文件 `backend/app.db` 里。

### 可选(推荐)

- **DB Browser for SQLite**(免费,图形界面看数据):https://sqlitebrowser.org
  - 也可用 VSCode 插件:「SQLite Viewer」或「SQLite3 Editor」

---

## 启动前端

```bash
cd frontend
npm install         # 首次需要,安装依赖
npm run dev         # 启动开发服务器
```

访问 http://localhost:5173

其他脚本:

```bash
npm run build       # 生产构建
npm run type-check  # TypeScript 类型检查
npm run lint        # 代码检查 + 修复(oxlint + eslint)
npm run format      # prettier 格式化 src/
```

---

## 启动后端

```bash
cd backend
pip install -r requirements.txt   # 首次需要,安装依赖
uvicorn app.main:app --reload      # 启动开发服务器
```

启动后可访问:

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/docs | Swagger 交互式接口文档 |
| http://127.0.0.1:8000/redoc | ReDoc 只读文档 |
| http://127.0.0.1:8000/api/health | 健康检查 → `{"status":"ok"}` |

- 日志文件:`backend/logs/app.log`(10MB 轮转,保留 7 天,zip 压缩)
- 数据库文件:`backend/app.db`(首次启动自动生成)

### 灌入演示数据(seed)

每人本地数据库数据相互独立。要**全员数据一致**(联调、演示用),运行 seed 脚本统一灌入:

```bash
cd backend
python -m app.seed --reset     # 删库重建 + 灌入演示数据(推荐)
python -m app.seed             # 只追加灌入(表已存在时)
```

任何时候数据乱了,重跑 `--reset` 立刻回到统一起点。

> **新增表后**:在 `backend/app/seed.py` 的 `seed()` 函数里按注释示例添加插入语句。

### 查看数据库

任选一种:
- **DB Browser for SQLite**:打开 `backend/app.db`
- **VSCode**:装「SQLite Viewer」插件,直接点开 `app.db`
- **命令行**:`sqlite3 backend/app.db`(Python 自带,直接进入 SQL 交互)

### 配置

默认值开箱即用。如需修改,在 `backend/` 下复制 `.env.example` 为 `.env`:

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

常用配置项:

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接 | `sqlite:///./app.db`(切 PostgreSQL 改这里) |
| `LOG_LEVEL` | 日志级别 | `INFO`(调试用 `DEBUG`) |
| `APP_NAME` | 应用名 | `AI 教学评价系统` |

---

## 后端开发约定

| 想做的事 | 在哪里 |
|----------|--------|
| 加接口 | `app/api/v1/` 下建文件,定义 `router`,在 `main.py` 里 `include_router` |
| 加数据表 | `app/models/` 下建文件定义 `SQLModel`,在 `models/__init__.py` 里 import,重启自动建表 |
| 加演示数据 | `app/seed.py` 的 `seed()` 函数 |
| 改配置 | `app/core/config.py`(或 `.env`) |
| 加中间件 | `app/main.py` |

## 算法侧

占位,待后续补充依赖与模型。

## 协作

- 主分支:`main`,开发分支:`dev`
- 详细任务分工与会议记录见 `docs/`
