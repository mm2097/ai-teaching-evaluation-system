"""知识点名称公共工具：复合名称拆分与规范化匹配。

课程测试模板（各题扣分情况）中，「扣分的主要知识点」一格可能写多个
知识点（如「传输时延、TCP/UDP协议」）。导入建点、扣分归属、失分率
统计、掌握度计算统一按本模块的拆分规则处理，保证口径一致。

拆分规则：
    - 按中文顿号「、」、全角/半角逗号、分号拆分
    - 不按「/」拆分（TCP/IP 等名称本身含斜杠）
    - 每个片段去首尾空白，空片段丢弃，重复片段去重（保持首次出现顺序）
"""
from __future__ import annotations

import re

_SPLIT_RE = re.compile(r"[、,，;；]+")

# 演示数据和历史题库曾使用过的同义名称统一映射到课程知识树中的规范名称。
_KNOWLEDGE_NAME_ALIASES = {
    "UDP 协议": "UDP 协议特点",
    "进程状态": "进程状态转换",
    "页面置换": "页面置换算法",
    "链表": "链表操作",
    "二叉树": "二叉树遍历",
    "图遍历": "图的遍历",
}


def canonicalize_knowledge_name(raw: str | None) -> str:
    """返回知识点的规范名称，消除同义标签造成的重复列。"""
    name = re.sub(r"\s+", " ", str(raw or "").strip())
    return _KNOWLEDGE_NAME_ALIASES.get(name, name)


def split_knowledge_names(raw: str | None) -> list[str]:
    """把一个知识点名称拆分为多个规范知识点名称。

    单名知识点原样返回（仅去空白）；空值/空白返回空列表。
    """
    if not raw or not str(raw).strip():
        return []
    pieces: list[str] = []
    for piece in _SPLIT_RE.split(str(raw)):
        name = piece.strip()
        if name and name not in pieces:
            pieces.append(name)
    return pieces
