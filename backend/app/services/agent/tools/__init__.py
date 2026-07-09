"""Agent 工具集合。

工具注册到全局 registry，由 base.py 在 FC 循环中调用。
分两类：
    queries.py   Agent A 学情查询（10 个，只读）
    exam.py      Agent B 组卷（读 + AI 生成）
"""
from __future__ import annotations

import threading

from app.services.agent.registry import get_registry

_lock = threading.Lock()
_registered = False


def register_all_tools() -> None:
    """注册全部工具到全局 registry（幂等，线程安全）。"""
    global _registered
    with _lock:
        if _registered:
            return
        from .queries import register_query_tools
        from .exam import register_exam_tools

        registry = get_registry()
        register_query_tools(registry)
        register_exam_tools(registry)
        _registered = True
