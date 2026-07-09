"""报告生成 API。

接口：
    GET  /api/v1/report/class       班级报告（模板兜底 + LLM 增强）
    GET  /api/v1/report/student     学生报告（模板兜底 + LLM 增强）
"""
from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlmodel import Session

from app.core.database import get_session
from app.services.report_template import (
    build_class_context,
    build_student_context,
    render_report,
)

router = APIRouter()

ALGO_BASE = "http://127.0.0.1:8001"


def _enhance_with_llm(scope: str, ctx_dict: dict, template: dict) -> dict:
    """调 algorithm 服务做 LLM 增强，失败回退模板。"""
    try:
        resp = httpx.post(
            f"{ALGO_BASE}/generate_report",
            json={
                "scope": scope,
                "template": template,
                "context": ctx_dict,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"LLM 报告增强失败，使用模板：{e}")
        return {**template, "source": "template_fallback", "error": str(e)[:200]}


@router.get("/report/class", tags=["报告生成"])
def get_class_report(
    course_id: int = Query(...),
    class_id: int | None = Query(default=None),
    use_llm: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict:
    """班级报告。模板必走，LLM 增强（失败回退模板）。"""
    ctx = build_class_context(session, course_id, class_id)
    template = render_report(ctx)

    if not use_llm:
        return template

    ctx_dict = _ctx_to_dict(ctx)
    return _enhance_with_llm("class", ctx_dict, template)


@router.get("/report/student", tags=["报告生成"])
def get_student_report(
    student_id: int = Query(...),
    course_id: int = Query(...),
    use_llm: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict:
    """学生报告。模板必走，LLM 增强（失败回退模板）。"""
    ctx = build_student_context(session, student_id, course_id)
    template = render_report(ctx)

    if not use_llm:
        return template

    ctx_dict = _ctx_to_dict(ctx)
    return _enhance_with_llm("student", ctx_dict, template)


def _ctx_to_dict(ctx) -> dict:
    """ReportContext → dict（给 algorithm 服务的 LLM prompt 用）。"""
    return {
        "scope": ctx.scope,
        "course_id": ctx.course_id,
        "course_name": ctx.course_name,
        "student_id": ctx.student_id,
        "student_name": ctx.student_name,
        "class_name": ctx.class_name,
        "avg_score": ctx.avg_score,
        "pass_rate": ctx.pass_rate,
        "excellent_rate": ctx.excellent_rate,
        "weak_points": ctx.weak_points,
        "strong_points": ctx.strong_points,
        "trend": ctx.trend,
        "risk_count": ctx.risk_count,
        "tags": ctx.tags,
        "radar": ctx.radar,
    }
