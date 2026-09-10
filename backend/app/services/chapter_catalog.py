"""课程章节规范化。

章节名称是课程知识模块的展示名称，不应直接使用大模型返回的自由文本。
统一从知识点所属模块和模块排序生成，避免同一课程出现多个同名章节。
"""
from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models import KnowledgeModule, KnowledgePoint


_CN_NUMBERS = "零一二三四五六七八九"


def _chapter_number(value: int) -> str:
    """将常见的模块排序号转成中文章节序号。"""
    if value < 1:
        return ""
    if value < 10:
        return _CN_NUMBERS[value]
    if value < 20:
        return f"十{_CN_NUMBERS[value - 10] if value > 10 else ''}"
    tens, ones = divmod(value, 10)
    return f"{_CN_NUMBERS[tens]}十{_CN_NUMBERS[ones] if ones else ''}"


def _compact(value: str | None) -> str:
    return re.sub(r"[\s、，,。:：·/_-]+", "", value or "").lower()


def canonical_chapter(
    session: Session,
    course_id: int,
    knowledge_point: str | None,
    raw_chapter: str | None = None,
) -> str:
    """根据课程知识点返回唯一章节名。

    先精确匹配知识点，再用文本匹配模块名，兼容导入数据和模型返回的别名。
    """
    modules = session.exec(
        select(KnowledgeModule)
        .where(KnowledgeModule.course_id == course_id)
        .order_by(KnowledgeModule.sort_num, KnowledgeModule.module_id)
    ).all()
    if not modules:
        return raw_chapter or ""

    module_by_id = {m.module_id: m for m in modules}
    point_text = _compact(knowledge_point)
    matched = None
    if point_text:
        point = session.exec(
            select(KnowledgePoint)
            .join(KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id)
            .where(
                KnowledgeModule.course_id == course_id,
                KnowledgePoint.point_name == (knowledge_point or ""),
            )
        ).first()
        if point:
            matched = module_by_id.get(point.module_id)

    # 对于题库/导入数据中知识点名称存在轻微格式差异的情况，按规范化文本兜底。
    if matched is None and point_text:
        for module in modules:
            if _compact(module.module_name) in point_text or point_text in _compact(module.module_name):
                matched = module
                break

    # 没有知识点记录时，仍尝试从模型返回的章节文本识别模块，避免产生别名。
    if matched is None and raw_chapter:
        chapter_text = _compact(raw_chapter)
        for module in modules:
            if _compact(module.module_name) in chapter_text:
                matched = module
                break

    if matched is None:
        return raw_chapter or ""

    number = _chapter_number(matched.sort_num)
    return f"第{number}章 {matched.module_name}" if number else matched.module_name

