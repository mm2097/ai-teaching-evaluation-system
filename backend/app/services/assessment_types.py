"""课程考核类型的统一名称与识别规则。"""
from __future__ import annotations

import re


ASSESSMENT_TYPE_LABELS = {
    "discussion": "课堂讨论成绩",
    "midterm": "期中考试成绩",
    "final": "期末考试成绩",
    "attendance": "课程考勤成绩",
    "homework": "平时作业成绩",
    "other": "其他过程性成绩",
    "participation": "课堂参与情况",
}

ACADEMIC_ASSESSMENT_TYPES = (
    "discussion",
    "midterm",
    "final",
    "attendance",
    "homework",
    "other",
)


def classify_assessment_type(data_type: str, batch_name: str | None = None) -> str:
    """按评价引擎现有关键字口径识别教学数据所属考核类型。"""
    if data_type == "attendance":
        return "attendance"
    if data_type == "participation":
        return "participation"

    name = batch_name or ""
    if "讨论" in name:
        return "discussion"
    if "期中" in name and "期末" not in name:
        return "midterm"
    if "期末" in name:
        return "final"
    if "作业" in name:
        return "homework"
    return "other"


def display_assessment_batch_name(assessment_type: str, batch_name: str | None) -> str:
    """生成面向学生的考核批次名，隐藏数据库、Excel 等导入方式。"""
    canonical = {
        "discussion": "课堂讨论",
        "midterm": "期中考试",
        "final": "期末考试",
        "attendance": "课程考勤",
        "homework": "平时作业",
        "participation": "课堂参与",
    }
    if assessment_type in canonical:
        return canonical[assessment_type]

    name = (batch_name or "").strip()
    name = re.sub(
        r"^(?:SQLite)?(?:多类型数据库|数据库多类型|数据库导入|数据库)[-_—\s]*",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    if "平时" in name:
        return "平时成绩"
    if "实验" in name:
        return "实验成绩"
    if "项目" in name or "课程设计" in name:
        return "课程项目成绩"
    if "测验" in name:
        return "课程测验"
    return name or "其他考核"


def display_assessment_type_name(assessment_type: str, batch_name: str | None) -> str:
    """显示具体成绩语义；评价中的 other 分组仍可细分为平时、实验或项目。"""
    if assessment_type != "other":
        return ASSESSMENT_TYPE_LABELS[assessment_type]
    batch_display = display_assessment_batch_name(assessment_type, batch_name)
    if batch_display.endswith("成绩"):
        return batch_display
    return ASSESSMENT_TYPE_LABELS[assessment_type]
