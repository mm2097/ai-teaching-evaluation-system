"""PDF 图表渲染：将报告快照 charts 数据渲染为 PNG，供 reportlab 嵌入导出的 PDF。

本模块把预览页 echarts 的图表样式（配色、坐标轴、比例、数据标签）迁移到
matplotlib（Agg 聚合后端，无 GUI）上，让下载的 PDF 与在线生成的预览观感一致。
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

try:
    import matplotlib

    matplotlib.use("Agg")  # 必须早于 pyplot 导入，避免依赖 GUI
    from matplotlib import font_manager
    from matplotlib import rcParams
    from matplotlib.figure import Figure

    _FONT_CANDIDATES = [
        r"C:\Windows\Fonts\simhei.ttf",    # 黑体
        r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simsun.ttc",    # 宋体
    ]
    for _path in _FONT_CANDIDATES:
        try:
            font_manager.fontManager.addfont(_path)
            break
        except Exception:
            continue
    rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "SimSun", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    rcParams["axes.edgecolor"] = "#cbd5e1"
    rcParams["text.color"] = "#334155"
    rcParams["axes.labelcolor"] = "#64748b"
    rcParams["xtick.color"] = "#64748b"
    rcParams["ytick.color"] = "#64748b"
    _MPL_OK = True
except Exception:  # pragma: no cover
    logger.warning("matplotlib 初始化失败，PDF 图形化数据将回退为表格", exc_info=True)
    _MPL_OK = False
    Figure = None

# —— 与前端 echarts option 一致的配色 ——
# 条/柱：<60 红，<80 橙，其余绿（学业构成第三档为蓝）
_SCORE_LOW = "#ef4444"
_SCORE_MID = "#f59e0b"
_SCORE_HIGH = "#10b981"
_SCORE_HIGH_PART = "#2563eb"
# 核心比率：>=85 绿，>=70 蓝，否则橙
_PIE_PALETTE = ["#ef4444", "#f97316", "#f59e0b", "#2563eb", "#10b981"]
_RATE_HIGH = "#10b981"
_RATE_MID = "#2563eb"
_RATE_LOW = "#f59e0b"
_BLUE = "#2563eb"


def _color_bar(v: float, high: str = _SCORE_HIGH) -> str:
    return _SCORE_LOW if v < 60 else (_SCORE_MID if v < 80 else high)


def _png(fig: Figure) -> bytes | None:
    """把 Figure 导出为 PNG 字节流；失败返回 None。"""
    if not _MPL_OK:
        return None
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white",
                    edgecolor="none")
        return buf.getvalue()
    except Exception as exc:  # pragma: no cover
        logger.warning("图表渲染失败: %s", exc)
        return None
    finally:
        try:
            fig.clf()
        except Exception:
            pass


def _clean(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _style_axes(ax, show_xlabel: str | None = None):
    """贴近 echarts 的极简坐标轴：隐藏上/右边线，只留轻网格。"""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#cbd5e1")
    ax.grid(axis="x", linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.tick_params(axis="both", labelsize=9)
    if show_xlabel:
        ax.set_xlabel(show_xlabel, fontsize=9)


def render_rate_bar(rates: dict) -> bytes | None:
    """核心比率：及格率 / 优秀率 / 出勤率（横向条形图，含%标签与分级配色）。"""
    items = [
        ("及格率", _clean(rates.get("passRate"))),
        ("优秀率", _clean(rates.get("excellentRate"))),
        ("出勤率", _clean(rates.get("attendanceRate"))),
    ]
    if not _MPL_OK:
        return None
    names = [n for n, _ in items]
    values = [v for _, v in items]
    colors = [_RATE_HIGH if v >= 85 else (_RATE_MID if v >= 70 else _RATE_LOW) for v in values]
    fig = _fig()
    ax = fig.subplots()
    bars = ax.barh(names, values, color=colors, height=0.62)
    ax.set_xlim(0, 100)
    ax.set_xlabel("占比 (%)", fontsize=9)
    _style_axes(ax)
    ax.set_xticks([0, 25, 50, 75, 100])
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{v:.0f}%", va="center", fontsize=9, color="#475569")
    fig.tight_layout()
    return _png(fig)


def render_score_pie(score_buckets: list) -> bytes | None:
    """成绩分布：分档人数（环形饼图，配色/百分比展示对齐 echarts）。"""
    data = [b for b in score_buckets if b.get("count")]
    if not data or not _MPL_OK:
        return None
    labels = [str(b.get("label", "")) for b in data]
    values = [_clean(b.get("count")) for b in data]
    colors = [_PIE_PALETTE[i % len(_PIE_PALETTE)] for i in range(len(data))]
    fig = Figure(figsize=(6.6, 4.2), dpi=110)
    ax = fig.subplots()
    ax.pie(values, labels=labels, autopct="%d%%", startangle=90,
           colors=colors, textprops={"fontsize": 9},
           wedgeprops={"width": 0.26, "edgecolor": "white", "linewidth": 2},
           pctdistance=0.78)
    # 图例放底部，贴近 echarts legend bottom
    ax.legend(labels, loc="upper center", bbox_to_anchor=(0.5, -0.06),
              ncol=min(len(labels), 5), fontsize=8, frameon=False)
    fig.tight_layout()
    return _png(fig)


def render_knowledge_bar(knowledge: list) -> bytes | None:
    """知识点掌握度（横向条形图，按掌握度升序，分级配色）。"""
    rows = sorted([k for k in knowledge], key=lambda x: _clean(x.get("accuracy")))
    if not rows or not _MPL_OK:
        return None
    names = [str(k.get("name", "")) for k in rows]
    values = [_clean(k.get("accuracy")) for k in rows]
    fig = Figure(figsize=(7.2, max(3.4, 0.32 * len(rows) + 1.2)), dpi=110)
    ax = fig.subplots()
    bars = ax.barh(names, values, height=0.6, color=[_color_bar(v) for v in values])
    ax.set_xlim(0, 100)
    ax.set_xlabel("掌握度 (%)", fontsize=9)
    ax.set_xticks([0, 25, 50, 75, 100])
    _style_axes(ax)
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{v:.0f}%", va="center", fontsize=8, color="#475569")
    fig.tight_layout()
    return _png(fig)


def render_radar(radar: dict) -> bytes | None:
    """能力维度雷达图（五边形/多边形，蓝色半透明填充对齐 echarts）。"""
    names = [str(k) for k in radar.keys()]
    values = [_clean(v) for v in radar.values()]
    if not names or not _MPL_OK:
        return None
    import numpy as np

    n = len(names)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]
    fig = Figure(figsize=(6.0, 5.2), dpi=110)
    ax = fig.add_subplot(projection="polar")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles)
    ax.set_xticklabels(names, fontsize=9, color="#64748b")
    ax.tick_params(colors="#64748b", labelsize=8)
    ax.plot(angles_closed, values_closed, color=_BLUE, linewidth=2)
    ax.fill(angles_closed, values_closed, color=_BLUE, alpha=0.15)
    # 分割背景，接近 echarts splitArea
    ax.grid(linestyle="--", alpha=0.4, color="#cbd5e1")
    for a, v in zip(angles, values):
        ax.annotate(f"{v:.0f}", xy=(a, v), xytext=(a, v + 8),
                    ha="center", fontsize=8, color=_BLUE)
    fig.tight_layout()
    return _png(fig)


def render_trend_line(score_history: list) -> bytes | None:
    """成绩走势折线图（蓝线+浅蓝填充，Y 轴 0-100）。"""
    rows = [h for h in score_history if h.get("score") is not None]
    if len(rows) < 2 or not _MPL_OK:
        return None
    names = [str(h.get("name", "")) for h in rows]
    values = [_clean(h.get("score")) for h in rows]
    fig = _fig()
    ax = fig.subplots()
    x = range(len(names))
    ax.plot(x, values, marker="o", color=_BLUE, linewidth=2)
    ax.fill_between(x, values, color=_BLUE, alpha=0.08)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15 if len(names) > 5 else 0, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("分数", fontsize=9)
    _style_axes(ax)
    ax.grid(axis="y", linestyle="--", alpha=0.4, color="#cbd5e1")
    ax.grid(axis="x", linestyle="none")
    for i, v in enumerate(values):
        ax.annotate(f"{v:.0f}", (i, v), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=8, color="#2563eb")
    fig.tight_layout()
    return _png(fig)


def _bar_rows(pairs: list, high: str = _SCORE_HIGH) -> bytes | None:
    """通用横向条形图（指标得分 / 学业构成），pairs: [(name, value)]。"""
    if not _MPL_OK:
        return None
    names = [str(n) for n, _ in pairs]
    values = [_clean(v) for _, v in pairs]
    fig = Figure(figsize=(7.2, max(3.0, 0.3 * len(pairs) + 1.0)), dpi=110)
    ax = fig.subplots()
    bars = ax.barh(names, values, height=0.6, color=[_color_bar(v, high=high) for v in values])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("得分", fontsize=9)
    _style_axes(ax)
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{v:.0f}", va="center", fontsize=8, color="#475569")
    fig.tight_layout()
    return _png(fig)


def render_index_bar(eval_indexes: list) -> bytes | None:
    """教师配置指标得分（横向条形图，分级配色）。"""
    pairs = [(it.get("name", ""), it.get("score")) for it in eval_indexes if it.get("score") is not None]
    if not pairs:
        return None
    return _bar_rows(pairs[::-1], high=_SCORE_HIGH)


def render_parts_bar(academic_parts: list) -> bytes | None:
    """学业构成（教师配比）得分（横向条形图，第三档蓝色）。"""
    pairs = [(it.get("name", ""), it.get("score")) for it in academic_parts if it.get("score") is not None]
    if not pairs:
        return None
    return _bar_rows(pairs, high=_SCORE_HIGH_PART)


def _fig() -> Figure:
    return Figure(figsize=(7.2, 3.5), dpi=110)