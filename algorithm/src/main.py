"""AI 算法服务 FastAPI 入口。

启动：
    cd algorithm
    uvicorn src.main:app --port 8001 --reload

接口：
    GET  /health              健康检查
    POST /generate_exercises  AI 出题
    POST /generate_report     报告 LLM 增强
    POST /agent/chat          Agent FC（同步版，给后端兜底用）
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from .config import get_settings
from .generator import generate_exercises
from .judge import judge_answer
from .reporter import enhance_report
from .schemas import ErrorResponse, GenerateRequest, GenerateResponse, JudgeRequest, JudgeResponse


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


# ===== B2 AI 判题 =====

@app.post(
    "/judge_answer",
    response_model=JudgeResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["AI 判题"],
)
def judge(req: JudgeRequest) -> JudgeResponse:
    """AI 判题主接口。

    对齐 MVP 验收测试集 TC-B2：简答题 AI 判分，给出依据。
    失败时返回 flag=manual_required 而非报错（TC-B2-08）。
    """
    s = get_settings()
    if not s.llm_api_key:
        # 无 Key 时返回需人工判分
        return JudgeResponse(
            total_score=None,
            rubric_points=[],
            confidence=None,
            reason="AI 服务未配置 API Key，需人工判分",
            flag="manual_required",
        )

    try:
        return judge_answer(req)
    except RuntimeError as e:
        logger.error(f"判题失败：{e}")
        # 判题失败不抛 5xx，返回 manual_required（对齐 TC-B2-08）
        return JudgeResponse(
            total_score=None,
            rubric_points=[],
            confidence=None,
            reason=f"AI 判分异常，需人工判分：{e}",
            flag="manual_required",
        )
    except Exception as e:
        logger.exception(f"判题未预期异常：{e}")
        return JudgeResponse(
            total_score=None,
            rubric_points=[],
            confidence=None,
            reason=f"AI 服务内部错误，需人工判分：{e}",
            flag="manual_required",
        )


# ===== D10 报告 LLM 增强 =====

class ReportRequestModel(BaseModel):
    """报告增强请求体。"""

    scope: str = Field(..., description="class / student")
    template: dict = Field(..., description="模板初稿 {summary, conclusion, suggestion}")
    context: dict = Field(..., description="结构化统计指标")


@app.post(
    "/generate_report",
    tags=["报告生成"],
)
def generate_report(req: ReportRequestModel) -> dict:
    """报告 LLM 增强接口。

    失败自动回退到模板文本（``source=template_fallback``），保证不抛 5xx。
    """
    s = get_settings()
    if not s.llm_api_key:
        # 无 Key 时直接返回模板回退
        return {
            "summary": req.template.get("summary", ""),
            "conclusion": req.template.get("conclusion", ""),
            "suggestion": req.template.get("suggestion", ""),
            "source": "template_fallback",
            "error": "AI 服务未配置 API Key",
        }
    try:
        return enhance_report(req.scope, req.template, req.context)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"报告增强异常：{e}")
        return {
            "summary": req.template.get("summary", ""),
            "conclusion": req.template.get("conclusion", ""),
            "suggestion": req.template.get("suggestion", ""),
            "source": "template_fallback",
            "error": str(e)[:200],
        }


# ===== Agent Function Calling 透传 =====

class AgentChatRequest(BaseModel):
    """Agent 单步 FC 请求体（透传给 LLM）。"""

    messages: list[dict] = Field(..., description="完整对话历史")
    tools: list[dict] = Field(default_factory=list, description="工具 schema")
    tool_choice: str = Field(default="auto")


@app.post(
    "/agent/chat",
    tags=["Agent"],
)
def agent_chat(req: AgentChatRequest) -> dict:
    """Agent 单步 FC 调用。

    后端 Agent 内核每步循环调用此接口：发 messages + tools → 拿 tool_calls 或 content。
    循环逻辑、工具执行都在 backend。
    """
    s = get_settings()
    if not s.llm_api_key:
        raise HTTPException(status_code=503, detail="AI 服务未配置 API Key，Agent 不可用")

    from .llm_client import get_llm_client
    try:
        client = get_llm_client()
        result = client.chat_with_tools(
            messages=req.messages,
            tools=req.tools,
            tool_choice=req.tool_choice,
        )
        return {
            "content": result.content,
            "tool_calls": result.tool_calls,
            "finish_reason": result.finish_reason,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
    except RuntimeError as e:
        logger.error(f"Agent FC 调用失败：{e}")
        raise HTTPException(status_code=503, detail=f"AI 服务暂不可用：{e}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Agent FC 未预期异常：{e}")
        raise HTTPException(status_code=500, detail=f"AI 服务内部错误：{e}")
