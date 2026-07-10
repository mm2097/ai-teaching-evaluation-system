"""报告生成 API。

接口：
    GET  /api/v1/report     统一报告接口（前端传 report_type，后端按类型组装）
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
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

# 报告类型 → scope 映射
_REPORT_TYPE_SCOPE: dict[int, str] = {
    1: "class",     # 班级学情分析报告
    2: "student",   # 学生个人学情报告
    3: "class",     # 课程知识点分析报告
    4: "class",     # 学生学习质量报告
}

_REPORT_TYPE_NAMES: dict[int, str] = {
    1: "班级学情分析报告",
    2: "学生个人学情报告",
    3: "课程知识点分析报告",
    4: "学生学习质量报告",
}


def _enhance_with_llm(scope: str, report_type: int, ctx_dict: dict, template: dict) -> dict:
    """调 algorithm 服务做 LLM 增强，失败回退模板。"""
    type_name = _REPORT_TYPE_NAMES.get(report_type, "报告")
    try:
        resp = httpx.post(
            f"{ALGO_BASE}/generate_report",
            json={
                "scope": scope,
                "report_type": report_type,
                "report_type_name": type_name,
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


@router.get("/report", tags=["报告生成"])
def get_report(
    course_id: int = Query(..., description="课程 ID"),
    report_type: int = Query(..., ge=1, le=4, description="报告类型：1=班级学情 2=学生个人 3=课程知识点 4=学习质量"),
    class_id: int | None = Query(default=None, description="班级 ID（report_type≠2 时可选）"),
    student_id: int | None = Query(default=None, description="学生 ID（report_type=2 时必填）"),
    use_llm: bool = Query(default=True, description="是否使用 LLM 增强"),
    session: Session = Depends(get_session),
) -> dict:
    """统一报告生成接口。

    前端传入 report_type，后端根据类型组装对应的统计数据并生成报告。
    """
    scope = _REPORT_TYPE_SCOPE.get(report_type, "class")
    type_name = _REPORT_TYPE_NAMES.get(report_type, "报告")

    # 参数校验
    if report_type == 2:
        if not student_id:
            raise HTTPException(status_code=400, detail="学生个人报告必须提供 student_id")
        ctx = build_student_context(session, student_id, course_id)
    else:
        ctx = build_class_context(session, course_id, class_id, report_type)

    ctx.scope = scope
    template = render_report(ctx)

    if not use_llm:
        return {**template, "report_type": report_type, "report_type_name": type_name}

    ctx_dict = _ctx_to_dict(ctx)
    ctx_dict["report_type"] = report_type
    ctx_dict["report_type_name"] = type_name
    return _enhance_with_llm(scope, report_type, ctx_dict, template)


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
