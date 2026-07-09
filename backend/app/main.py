from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.users import router as users_router
from app.api.v1.courses import router as courses_router
from app.api.v1.students import router as students_router
from app.api.v1.scores import router as scores_router
from app.api.v1.dicts import router as dicts_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.logs import router as logs_router
from app.api.v1.evaluations import router as eval_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.teaching_data import router as teaching_data_router
from app.api.v1.quiz import router as quiz_router
from app.api.v1.question_bank import router as question_bank_router
from app.api.v1.agent import router as agent_router
from app.api.v1.report import router as report_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动:初始化日志 + 建表
    setup_logging()
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 辅助教学评价系统后端 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["健康检查"])
app.include_router(auth_router, prefix="/api", tags=["认证"])
app.include_router(users_router, prefix="/api", tags=["用户管理"])
app.include_router(courses_router, prefix="/api/v1", tags=["课程管理"])
app.include_router(students_router, prefix="/api/v1", tags=["学生管理"])
app.include_router(scores_router, prefix="/api/v1", tags=["成绩管理"])
app.include_router(dicts_router, prefix="/api/v1", tags=["字典"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["看板"])
app.include_router(analysis_router, prefix="/api/v1", tags=["学情分析"])
app.include_router(logs_router, prefix="/api/v1", tags=["系统日志"])
app.include_router(eval_router, prefix="/api/v1", tags=["评价管理"])
app.include_router(attendance_router, prefix="/api/v1", tags=["考勤管理"])
app.include_router(teaching_data_router, prefix="/api/v1", tags=["教学数据"])
app.include_router(quiz_router, prefix="/api/v1", tags=["答题管理"])
app.include_router(question_bank_router, prefix="/api/v1", tags=["题库管理"])
app.include_router(agent_router, prefix="/api/v1", tags=["AI Agent"])
app.include_router(report_router, prefix="/api/v1", tags=["报告生成"])
