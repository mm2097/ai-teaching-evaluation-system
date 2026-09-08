"""Agent API：学情问答与组卷 Agent。

接口：
    POST /api/v1/agent/chat         同步版（等待完整结果）
    POST /api/v1/agent/chat/stream  SSE 流式（实时推送工具调用过程）
    GET  /api/v1/agent/tools        查看已注册工具（调试用）
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.v1.analysis import _check_course_access, _check_profile_access
from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.core.permissions import ensure_roles, require_teacher, require_teaching_user
from app.models import SysUser
from app.services.agent.base import run_agent, run_agent_stream
from app.services.agent.registry import get_registry
from app.services.agent.tools import register_all_tools

router = APIRouter()


class AgentChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(..., description="用户问题")
    course_id: int | None = Field(default=None, description="当前课程上下文")
    student_id: int | None = Field(default=None, description="当前学生上下文")
    session_id: str | None = Field(default=None, description="会话 ID（跨轮保持上下文）")
    agent_type: str = Field(default="qa", description="qa=学情问答 / exam=组卷 / diagnosis=AI 学情诊断")
    max_steps: int = Field(default=5, ge=1, le=10)


class AgentChatResponse(BaseModel):
    answer: str
    steps: list[dict] = Field(default_factory=list)
    total_elapsed_ms: int = 0
    total_tokens: int = 0
    truncated: bool = False
    error: str | None = None


def _session_factory():
    """产生新 Session 的工厂（供 base.py 每步独立事务）。"""
    from app.core.database import engine
    return Session(engine)


def _check_diagnosis_access(
    session: Session, current_user: SysUser, req: "AgentChatRequest"
) -> None:
    """diagnosis 为教师专用：校验课程授课权 + 学生归属。

    仅对 agent_type=="diagnosis" 生效，qa/exam/tutor 维持原行为（不校验）。
    复用 analysis 的权限函数（注意参数顺序差异）：
      _check_course_access(session, current_user, course_id)       # session 在前
      _check_profile_access(current_user, student_id, course_id, session)  # session 在后
    校验失败抛 HTTPException，调用方需在 try 外调用或在 except HTTPException 中透传。
    _check_course_access 内部已拒绝 student/admin 角色，无需额外 require_teacher。
    """
    if req.agent_type != "diagnosis":
        return
    if req.course_id:
        _check_course_access(session, current_user, req.course_id)
    if req.student_id:
        _check_profile_access(current_user, req.student_id, req.course_id, session)


@router.post("/agent/chat", response_model=AgentChatResponse, tags=["Agent"])
def agent_chat(
    req: AgentChatRequest,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> AgentChatResponse:
    """同步版 Agent 对话（阻塞等待完整结果）。

    user_id 从当前 JWT 登录用户解析。

    diagnosis 为教师专用，校验课程与学生访问权限；qa/exam/tutor 维持原行为。
    """
    _ensure_registered()
    user_id = current_user.user_id

    # 仅 diagnosis 做权限校验（教师授课课程 + 课程内学生），HTTPException 直接抛出
    _check_diagnosis_access(session, current_user, req)

    try:
        result = run_agent(
            session_factory=_session_factory,
            user_message=req.message,
            user_id=user_id,
            course_id=req.course_id,
            student_id=req.student_id,
            session_id=req.session_id,
            agent_type=req.agent_type,
            max_steps=req.max_steps,
        )
        return AgentChatResponse(**result.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Agent chat 异常：{e}")
        return AgentChatResponse(
            answer=f"处理时遇到异常：{type(e).__name__}: {e}",
            steps=[],
            total_elapsed_ms=0,
            total_tokens=0,
            truncated=False,
            error=str(e)[:500],
        )


@router.post("/agent/chat/stream", tags=["Agent"])
def agent_chat_stream(
    req: AgentChatRequest,
    current_user: SysUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """SSE 流式版：实时推送工具调用过程，最后推送最终答案。

    diagnosis 权限校验在 event_stream 之外执行，403/404 在 SSE 建立前以正常 HTTP 响应返回。
    """
    _ensure_registered()
    user_id = current_user.user_id

    # 仅 diagnosis 做权限校验，HTTPException 在生成器之外抛出（不进 SSE 流）
    _check_diagnosis_access(session, current_user, req)

    def event_stream():
        try:
            for event in run_agent_stream(
                session_factory=_session_factory,
                user_message=req.message,
                user_id=user_id,
                course_id=req.course_id,
                student_id=req.student_id,
                session_id=req.session_id,
                agent_type=req.agent_type,
                max_steps=req.max_steps,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            logger.exception(f"SSE 异常：{e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agent/tools", tags=["Agent"])
def list_tools(
    current_user: SysUser = Depends(require_teacher),
) -> dict:
    """列出已注册的 Agent 工具（调试用）。"""
    _ensure_registered()
    registry = get_registry()
    tools = registry.list_for_agent("both", include_mutation=True)
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
            }
            for t in tools
        ],
        "count": len(tools),
    }


@router.delete("/agent/session/{session_id}", tags=["Agent"])
def clear_session(
    session_id: str,
    current_user: SysUser = Depends(require_teaching_user),
    session: Session = Depends(get_session),
) -> dict:
    """清空会话记忆。"""
    from app.services.agent.memory import clear_session as _clear, delete_persisted_session
    _clear(session_id, current_user.user_id)
    delete_persisted_session(session_id, current_user.user_id, session)
    return {"status": "ok", "session_id": session_id}


_registered = False


def _ensure_registered() -> None:
    global _registered
    if not _registered:
        register_all_tools()
        _registered = True
