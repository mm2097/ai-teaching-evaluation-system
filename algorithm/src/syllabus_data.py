"""教学大纲考核点数据(模块级常量,进程加载时解析一次)。

本模块在 import 时解析 ``docs/参考资料/Net教学大纲.docx`` 得到计网课程考核点,
供 :mod:`verifier` 做考核点对齐验证。本期硬编码计网一门(course_id=1)。

设计:
    - 解析失败时返回空列表并 log warning,不抛异常——保证 algorithm 服务能启动,
      verifier 见空列表会走「无大纲」降级(只做 TF-IDF 召回,不做关键词对齐)。
    - 路径解析:优先环境变量 SYLLABUS_PATH,其次相对仓库根的 docs/参考资料,
      再次 algorithm 同级的 ../docs/参考资料。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from loguru import logger

from .syllabus_parser import CheckPoint, parse_assessment, parse_course_objectives, parse_syllabus

# 计网大纲默认路径候选(按优先级)
_REPO_ROOT = Path(__file__).resolve().parents[2]  # algorithm/src/..  => 仓库根
_DEFAULT_CANDIDATES = [
    _REPO_ROOT / "docs" / "参考资料" / "Net教学大纲.docx",
    _REPO_ROOT.parent / "docs" / "参考资料" / "Net教学大纲.docx",
    Path(__file__).resolve().parent.parent.parent / "docs" / "参考资料" / "Net教学大纲.docx",
]


def _resolve_syllabus_path() -> Path | None:
    """解析大纲文件路径:环境变量 > 候选路径。找不到返回 None。"""
    env_path = os.environ.get("SYLLABUS_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        logger.warning(f"SYLLABUS_PATH 指向的文件不存在: {env_path}")

    for cand in _DEFAULT_CANDIDATES:
        if cand.exists():
            return cand
    return None


@lru_cache(maxsize=1)
def get_network_checkpoints() -> list[CheckPoint]:
    """获取计网课程考核点(进程内缓存)。

    文件缺失或解析失败时返回空列表,不抛异常。
    """
    path = _resolve_syllabus_path()
    if path is None:
        logger.warning(
            "未找到教学大纲文件,验证层将走无大纲降级模式(仅 TF-IDF 召回)。"
            f"候选路径: {_DEFAULT_CANDIDATES}"
        )
        return []
    return parse_syllabus(path)


@lru_cache(maxsize=1)
def get_course_objectives() -> list[dict[str, str]]:
    """获取课程目标 CT1-CT8(可选,供细粒度能力层级校验)。"""
    path = _resolve_syllabus_path()
    if path is None:
        return []
    return parse_course_objectives(path)


@lru_cache(maxsize=1)
def get_assessment_method() -> str:
    """获取考核方式文本。"""
    path = _resolve_syllabus_path()
    if path is None:
        return ""
    return parse_assessment(path)


def checkpoints_for_course(course_id: int) -> list[CheckPoint]:
    """按 course_id 取考核点。本期只支持 course_id=1(计网)。"""
    if course_id == 1:
        return get_network_checkpoints()
    # 其他课程本期无大纲,返回空(验证层降级)
    return []
