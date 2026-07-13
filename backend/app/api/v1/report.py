"""报告生成 API（Report.Generate / Report.Export / Report.Preview）。

接口：
    GET  /api/v1/report           生成报告 JSON
    GET  /api/v1/report/preview   在线预览 HTML
    GET  /api/v1/report/export    导出 Excel（format=xlsx）

数据源仅含成绩、考勤、课堂互动及教师发布题目的答题数据。
"""

from __future__ import annotations

import io as _io
from urllib.parse import quote

import httpx
import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Query as QueryParam
from fastapi.responses import HTMLResponse, Response
from loguru import logger
from sqlmodel import Session

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import SysUser
from app.api.v1.analysis import _check_course_access
from app.services.report_template import (
    build_class_context,
    build_student_context,
    render_report,
)

router = APIRouter()

ALGO_BASE = "http://127.0.0.1:8001"

_REPORT_TYPE_SCOPE: dict[int, str] = {
    1: "class",
    2: "student",
    3: "class",
    4: "class",
}

_REPORT_TYPE_NAMES: dict[int, str] = {
    1: "班级学情分析报告",
    2: "学生个人学情报告",
    3: "课程知识点分析报告",
    4: "学生学习质量报告",
}


# ============================================================================
# 工具函数
# ============================================================================

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
    except Exception as e:
        logger.warning(f"LLM report enhancement failed, using template: {e}")
        return {**template, "source": "template_fallback", "error": str(e)[:200]}


def _ctx_to_dict(ctx) -> dict:
    """ReportContext → dict。"""
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


def _assemble_report(
    session: Session,
    course_id: int,
    report_type: int,
    class_id: int | None,
    student_id: int | None,
    use_llm: bool,
) -> tuple[dict, any]:
    """组装报告 JSON 和上下文对象。返回 (report_dict, ReportContext)。"""
    scope = _REPORT_TYPE_SCOPE.get(report_type, "class")
    type_name = _REPORT_TYPE_NAMES.get(report_type, "报告")

    # Unwrap Query params（直接 Python 调用兼容）
    _class_id = class_id if not isinstance(class_id, QueryParam) else None
    _student_id = student_id if not isinstance(student_id, QueryParam) else None

    if report_type == 2:
        if not _student_id:
            raise HTTPException(status_code=400, detail="学生个人报告必须提供 student_id")
        ctx = build_student_context(session, _student_id, course_id)
    elif report_type == 4 and _student_id:
        ctx = build_student_context(session, _student_id, course_id)
        scope = "student"
    else:
        ctx = build_class_context(session, course_id, _class_id, report_type)

    ctx.scope = scope
    template = render_report(ctx)

    if not use_llm:
        return {**template, "report_type": report_type, "report_type_name": type_name}, ctx

    ctx_dict = _ctx_to_dict(ctx)
    ctx_dict["report_type"] = report_type
    ctx_dict["report_type_name"] = type_name
    return _enhance_with_llm(scope, report_type, ctx_dict, template), ctx


# ============================================================================
# 1. 报告生成（JSON）—— Report.Generate
# ============================================================================

@router.get("/report", tags=["报告生成"])
def get_report(
    course_id: int = Query(..., description="课程 ID"),
    report_type: int = Query(..., ge=1, le=4, description="报告类型：1=班级学情 2=学生个人 3=课程知识点 4=学习质量"),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    use_llm: bool = Query(default=True, description="是否使用 LLM 增强"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """统一报告生成接口（Report.Generate）。

    权限（Report.UserValid）：仅管理员和课程授课教师可生成报告。
    """
    _check_course_access(session, current_user, course_id)

    report, _ = _assemble_report(session, course_id, report_type, class_id, student_id, use_llm)
    return report


# ============================================================================
# 2. 在线预览（HTML）—— Report.Preview
# ============================================================================

_PREVIEW_CSS = """
<style>
  body { font-family: 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333; }
  h1 { text-align: center; font-size: 22px; border-bottom: 2px solid #1890ff; padding-bottom: 12px; }
  h2 { font-size: 16px; color: #1890ff; margin-top: 28px; border-left: 4px solid #1890ff; padding-left: 10px; }
  .meta { text-align: center; color: #888; font-size: 13px; margin-bottom: 24px; }
  .card { background: #fafafa; border-radius: 8px; padding: 16px 20px; margin: 12px 0; line-height: 1.8; }
  .stats { display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }
  .stat-item { flex: 1; min-width: 100px; background: #e6f7ff; border-radius: 6px; padding: 12px; text-align: center; }
  .stat-value { font-size: 24px; font-weight: bold; color: #1890ff; }
  .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
  .weak { color: #f5222d; }
  .strong { color: #52c41a; }
  .footer { text-align: center; color: #bbb; font-size: 12px; margin-top: 40px; border-top: 1px solid #eee; padding-top: 16px; }
</style>
"""


@router.get("/report/preview", tags=["报告生成"])
def preview_report(
    course_id: int = Query(...),
    report_type: int = Query(..., ge=1, le=4),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    use_llm: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> HTMLResponse:
    """报告在线预览 HTML 页面（Report.Preview）。

    返回可直接在浏览器中展示的完整 HTML 页面。

    权限（Report.UserValid）：仅管理员和课程授课教师可预览报告。
    """
    _check_course_access(session, current_user, course_id)

    report, ctx = _assemble_report(session, course_id, report_type, class_id, student_id, use_llm)
    type_name = _REPORT_TYPE_NAMES.get(report_type, "报告")

    # 核心指标卡片
    stat_cards = ""
    if ctx.avg_score:
        stat_cards += f'<div class="stat-item"><div class="stat-value">{ctx.avg_score}</div><div class="stat-label">均分</div></div>'
    if ctx.pass_rate:
        stat_cards += f'<div class="stat-item"><div class="stat-value">{ctx.pass_rate}%</div><div class="stat-label">及格率</div></div>'
    if ctx.excellent_rate:
        stat_cards += f'<div class="stat-item"><div class="stat-value">{ctx.excellent_rate}%</div><div class="stat-label">优秀率</div></div>'

    weak_html = ""
    if ctx.weak_points:
        items = "".join(f'<span class="weak">{p}</span>、' for p in ctx.weak_points[:5]).rstrip("、")
        weak_html = f"<p>🔴 薄弱知识点：{items}</p>"
    strong_html = ""
    if ctx.strong_points:
        items = "".join(f'<span class="strong">{p}</span>、' for p in ctx.strong_points[:5]).rstrip("、")
        strong_html = f"<p>🟢 优势知识点：{items}</p>"

    tags_html = ""
    if ctx.tags:
        tags_html = f"<p>🏷️ 标签：{'、'.join(ctx.tags)}</p>"

    radar_html = ""
    if ctx.radar:
        rows = "".join(
            f'<tr><td>{k}</td><td style="width:200px"><progress value="{v}" max="100" style="width:100%"></progress></td><td>{v}</td></tr>'
            for k, v in ctx.radar.items()
        )
        radar_html = f'<table style="width:100%">{rows}</table>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{type_name} - {ctx.course_name}</title>{_PREVIEW_CSS}</head>
<body>
<h1>{type_name}</h1>
<div class="meta">
  📚 课程：{ctx.course_name}
  {"| 👨‍🎓 学生：" + ctx.student_name if ctx.student_name else ""}
  {"| 🏫 班级：" + ctx.class_name if ctx.class_name else ""}
  | 📅 生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

<h2>📊 核心指标</h2>
<div class="stats">{stat_cards}</div>

<h2>📈 分析摘要</h2>
<div class="card">{report.get("summary", "")}</div>

<h2>🔍 分析结论</h2>
<div class="card">
  {report.get("conclusion", "")}
  {weak_html}
  {strong_html}
  {tags_html}
</div>

{("<h2>🎯 能力雷达</h2><div class='card'>" + radar_html + "</div>") if radar_html else ""}

<h2>💡 优化建议</h2>
<div class="card">{report.get("suggestion", "")}</div>

<div class="footer">
  AI 辅助教学评价系统 · {type_name} · 数据源：成绩、考勤、课堂互动、答题记录
</div>
</body></html>"""

    return HTMLResponse(content=html)


# ============================================================================
# 3. Excel 导出 —— Report.Export
# ============================================================================

@router.get("/report/export", tags=["报告生成"])
def export_report(
    course_id: int = Query(...),
    report_type: int = Query(..., ge=1, le=4),
    format: str = Query(default="xlsx", description="导出格式：xlsx"),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    use_llm: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> Response:
    """报告导出为 Excel 文件（Report.Export）。

    生成结构化的 .xlsx 工作簿，包含：
    - Sheet1: 报告正文（摘要/结论/建议）
    - Sheet2: 核心指标数据
    - Sheet3: 知识点详情（如有）

    权限（Report.UserValid）：仅管理员和课程授课教师可导出报告。
    """
    _check_course_access(session, current_user, course_id)

    report, ctx = _assemble_report(session, course_id, report_type, class_id, student_id, use_llm)
    type_name = _REPORT_TYPE_NAMES.get(report_type, "报告")

    wb = openpyxl.Workbook()

    # ── 样式 ──
    header_fill = openpyxl.styles.PatternFill(start_color="1890FF", end_color="1890FF", fill_type="solid")
    header_font_white = openpyxl.styles.Font(bold=True, size=12, color="FFFFFF")
    title_font = openpyxl.styles.Font(bold=True, size=14)
    wrap_align = openpyxl.styles.Alignment(wrap_text=True, vertical="top")

    def _write_sheet(ws, rows: list[list], col_widths: list[int] | None = None):
        for ri, row in enumerate(rows, start=1):
            for ci, val in enumerate(row, start=1):
                cell = ws.cell(row=ri, column=ci, value=val)
                if ri == 1:
                    cell.font = header_font_white
                    cell.fill = header_fill
                cell.alignment = wrap_align
        if col_widths:
            for ci, w in enumerate(col_widths, start=1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = w

    # ── Sheet 1: 报告正文 ──
    ws1 = wb.active
    ws1.title = "报告正文"
    now_str = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
    ws1.merge_cells("A1:C1")
    ws1.cell(row=1, column=1, value=type_name).font = title_font
    ws1.cell(row=2, column=1, value=f"课程：{ctx.course_name}  |  "
             f"学生：{ctx.student_name or '班级整体'}  |  "
             f"生成时间：{now_str}")

    rows1 = [
        ["章节", "标题", "内容"],
        ["一", "摘要", report.get("summary", "")],
        ["二", "结论", report.get("conclusion", "")],
        ["三", "建议", report.get("suggestion", "")],
    ]
    for ri, row in enumerate(rows1, start=3):
        for ci, val in enumerate(row, start=1):
            ws1.cell(row=ri, column=ci, value=val).alignment = wrap_align
    for ci in range(1, len(rows1[0]) + 1):
        cell = ws1.cell(row=3, column=ci)
        cell.font = header_font_white
        cell.fill = header_fill
    ws1.column_dimensions['A'].width = 8
    ws1.column_dimensions['B'].width = 10
    ws1.column_dimensions['C'].width = 80

    # ── Sheet 2: 核心指标 ──
    ws2 = wb.create_sheet("核心指标")
    rows2 = [
        ["指标", "数值", "说明"],
        ["班级均分", ctx.avg_score, "最近一次考核的班级平均分"],
        ["及格率", f"{ctx.pass_rate}%", "成绩 ≥ 60 分占比"],
        ["优秀率", f"{ctx.excellent_rate}%", "成绩 ≥ 85 分占比"],
        ["成绩趋势", ctx.trend, "基于历次成绩的回归斜率判断"],
        ["标签", "、".join(ctx.tags) if ctx.tags else "无", "自动生成的学习特征标签"],
    ]
    _write_sheet(ws2, rows2, col_widths=[16, 14, 45])

    # ── Sheet 3: 知识点详情 ──
    if ctx.weak_points or ctx.strong_points:
        ws3 = wb.create_sheet("知识点详情")
        rows3 = [["类型", "知识点"]]
        for pt in ctx.weak_points:
            rows3.append(["薄弱", pt])
        for pt in ctx.strong_points:
            rows3.append(["优势", pt])
        _write_sheet(ws3, rows3, col_widths=[10, 40])

    # ── 雷达图数据（学生报告时）──
    if ctx.radar:
        ws4 = wb.create_sheet("能力雷达")
        rows4 = [["维度", "得分(0-100)"]]
        for k, v in ctx.radar.items():
            rows4.append([k, v])
        _write_sheet(ws4, rows4, col_widths=[20, 16])

    output = _io.BytesIO()
    wb.save(output)
    output.seek(0)

    ctx_name = ctx.student_name or ctx.class_name or "班级"
    safe_name = f"{type_name}_{ctx.course_name}_{ctx_name}.xlsx"
    encoded = quote(safe_name, safe="")
    ascii_name = f"report_type{report_type}.xlsx"

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{encoded}"
            ),
        },
    )
