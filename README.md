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
| 算法 | Python(FastAPI + openai SDK + pydantic-settings),独立进程 8001 端口 |

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

## 算法侧(AI 服务)

独立 FastAPI 进程,跑在 8001 端口。提供 AI 出题、AI 判题、报告生成、Agent 问答能力,后端通过 HTTP 调用它。

> ⚠️ 必须用 `algorithm/.venv` 的虚拟环境,不能用全局 Python(全局 pydantic v1 会报错)。

### 启动算法服务

```bash
cd algorithm
.venv/Scripts/python.exe -m uvicorn src.main:app --port 8001 --reload
```

启动后访问:

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8001/health | 健康检查 + 查看当前模型/Key 配置状态 |
| http://127.0.0.1:8001/docs | Swagger 接口文档 |

### 配置 LLM 模型(关键)

算法服务通过 OpenAI 兼容协议接入大模型,**配置只需改一个 `.env` 文件**。

**第一步:创建配置文件**

```bash
cd algorithm
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

**第二步:编辑 `.env`,填入厂商和 API Key**

当前已接入 **DeepSeek**(默认),完整配置示例:

```env
# ---------- LLM 厂商配置 ----------
LLM_PROVIDER=deepseek

# API Key(在厂商控制台申请)
LLM_API_KEY=sk-你的真实Key

# Base URL(OpenAI 兼容端点,不同厂商不同)
LLM_BASE_URL=https://api.deepseek.com/v1

# 模型名
LLM_MODEL=deepseek-chat

# ---------- 调用参数 ----------
LLM_TIMEOUT=30          # 单次调用超时(秒)
LLM_MAX_RETRY=2         # 失败重试次数
LLM_TEMPERATURE=0.7     # 采样温度(0-1,出题推荐 0.7)
LLM_MAX_TOKENS=4000     # 单次最大输出 token

# ---------- 服务配置 ----------
AI_SERVICE_PORT=8001
AI_CORS_ORIGINS=http://localhost:5173,http://localhost:8000
```

### 支持的厂商切换

改 `.env` 里的 `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL` 三项即可切换:

| 厂商 | PROVIDER | BASE_URL | MODEL | 申请 Key |
|------|----------|----------|-------|---------|
| **DeepSeek**(当前默认) | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat`(V3) / `deepseek-reasoner`(R1) | https://platform.deepseek.com/api_keys |
| 通义千问(阿里) | `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` / `qwen-turbo` | https://dashscope.console.aliyun.com |
| 智谱 GLM | `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`(免费) / `glm-4` | https://open.bigmodel.cn |
| OpenAI(需科学上网) | `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` / `gpt-4o` | https://platform.openai.com |

> **变更后必须重启算法服务**(`.env` 在进程启动时读一次,Ctrl+C 后重新启动命令)。

### 算法服务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查,返回当前 provider/model/api_key_configured |
| POST | `/generate_exercises` | AI 出题(支持单选/多选/判断/填空/简答 5 种题型) |
| POST | `/judge_answer` | AI 判简答题(返回分数 + rubric 逐项打分 + 置信度) |
| POST | `/generate_report` | 生成学情报告结论(模板兜底 + LLM 增强) |
| POST | `/agent/chat` | Agent 对话(学情问答 / 组卷,调工具查数据库) |

### 验证 LLM 是否连通

启动算法服务后,跑一次出题测试:

```bash
# Windows PowerShell 用 ConvertTo-Json 生成 payload
curl -X POST http://localhost:8001/generate_exercises ^
  -H "Content-Type: application/json" ^
  -d "{\"course_id\":1,\"course_name\":\"数据结构\",\"knowledge_points\":[\"栈\"],\"question_types\":{\"single_choice\":1},\"difficulty\":\"medium\"}"
```

返回包含 `questions` 数组即成功。若返回 `403 AllocationQuota.FreeTierOnly`,说明该厂商免费额度已耗尽,需充值或换 Key。

### 三服务全链路

完整链路:浏览器(5173) → 后端(8000) → 算法服务(8001) → LLM 厂商

| 服务 | 端口 | 启动命令 |
|------|------|----------|
| 前端 | 5173 | `cd frontend && npm run dev` |
| 后端 | 8000 | `cd backend && uvicorn app.main:app --reload` |
| 算法 | 8001 | `cd algorithm && .venv/Scripts/python.exe -m uvicorn src.main:app --port 8001 --reload` |

## 协作

- 主分支:`main`,开发分支:`dev`
- 详细任务分工与会议记录见 `docs/`
