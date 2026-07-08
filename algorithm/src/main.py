"""AI 算法服务 FastAPI 入口。

启动：
    cd algorithm
    uvicorn src.main:app --port 8001 --reload

接口：
    GET  /health              健康检查
    POST /generate_exercises  AI 出题
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import get_settings
from .generator import generate_exercises
from .schemas import ErrorResponse, GenerateRequest, GenerateResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动前打印配置摘要。"""
    s = get_settings()
    logger.info(
        f"AI 算法服务启动 provider={s.llm_provider} model={s.llm_model} "
        f"base_url={s.llm_base_url} port={s.ai_service_port}"
    )
    if not s.llm_api_key:
        logger.warning("LLM_API_KEY 未配置，出题接口将返回 503")
    yield
    logger.info("AI 算法服务关闭")


app = FastAPI(
    title="AI 教学评价 - 算法服务",
    version="1.0.0",
    description="AI 出题、报告生成等 LLM 能力服务",
    lifespan=lifespan,
)

# ===== CORS：允许后端与前端跨源调用 =====
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["运维"])
def health() -> dict:
    """健康检查。后端通过此接口判断 AI 服务是否存活。"""
    s = get_settings()
    return {
        "status": "ok",
        "provider": s.llm_provider,
        "model": s.llm_model,
        "api_key_configured": bool(s.llm_api_key),
    }


@app.post(
    "/generate_exercises",
    response_model=GenerateResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["AI 出题"],
)
def generate(req: GenerateRequest) -> GenerateResponse:
    """AI 出题主接口。

    后端业务层调用此接口，传入课程、知识点、题型分布等，
    返回结构化题目列表与生成元信息。
    """
    # 基础参数校验（总数 1-30）
    total = req.total_count
    if total < 1 or total > 30:
        raise HTTPException(status_code=400, detail=f"题目总数须在 1-30 之间，当前 {total}")

    s = get_settings()
    if not s.llm_api_key:
        raise HTTPException(status_code=503, detail="AI 服务未配置 API Key，无法出题")

    try:
        return generate_exercises(req)
    except RuntimeError as e:
        # LLM 调用失败、JSON 解析失败等可恢复错误
        logger.error(f"出题失败：{e}")
        raise HTTPException(status_code=503, detail=f"AI 服务暂不可用：{e}")
    except Exception as e:
        # 未预期错误
        logger.exception(f"出题未预期异常：{e}")
        raise HTTPException(status_code=500, detail=f"AI 服务内部错误：{e}")
