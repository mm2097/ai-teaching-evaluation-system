"""课程目标(CT)达成度常量定义（不落库）。

来源：docs/参考资料/Net教学大纲.docx 表1（CT1-CT8 定义）与表3（章节→CT 矩阵）。
本期硬编码计算机网络一门(course_id=1)，与 algorithm/src/syllabus_data.py 决策一致。
"""
from __future__ import annotations

# CT 编号列表（固定顺序，CT1-CT8）
CT_CODES: list[str] = [f"CT{i}" for i in range(1, 9)]

# CT1-CT8 定义：编号 -> {类别, 描述}
CT_DEFINITIONS: dict[str, dict[str, str]] = {
    "CT1": {"category": "知识", "desc": "掌握计算机网络通信技术基本原理、重要术语和基本方法"},
    "CT2": {"category": "知识", "desc": "掌握网络体系结构TCP/IP分层技术的原理、协议、网络拓扑结构"},
    "CT3": {"category": "知识", "desc": "掌握IPV4网络地址划分方法和主流局域网技术"},
    "CT4": {"category": "能力", "desc": "具备分析计算机网络问题并通过掌握的方法解决问题的能力"},
    "CT5": {"category": "能力", "desc": "具备使用网络测量工具从工程角度观察和分析因特网协议执行过程的能力"},
    "CT6": {"category": "能力", "desc": "具备编程实现计算机网络基本算法和协议的能力"},
    "CT7": {"category": "素养", "desc": "具备良好科学素质、爱国精神、社会责任感和职业道德"},
    "CT8": {"category": "素养", "desc": "具备良好的团队协作精神"},
}

# 章节代码 -> 该章节支撑的 CT 列表（大纲表3）
# ch1=概论 ch2=应用层 ch3=传输层 ch4=网络层 ch5=链路层
# discussion=小班讨论 experiment=课程实验 design=课程设计
CHAPTER_CT_MAP: dict[str, list[str]] = {
    "ch1": ["CT1"],
    "ch2": ["CT1", "CT2", "CT4"],
    "ch3": ["CT1", "CT2", "CT4"],
    "ch4": ["CT1", "CT2", "CT3", "CT4"],
    "ch5": ["CT1", "CT2", "CT3", "CT4"],
    "discussion": ["CT4", "CT5", "CT6", "CT7", "CT8"],
    "experiment": ["CT4", "CT5", "CT6", "CT7", "CT8"],
    "design": ["CT4", "CT5", "CT6", "CT7", "CT8"],
}

# 考核批次类型(batch_type) -> CT 归因权重
# 1=平时(测验/作业) 2=实验 3=期中 4=期末 5=考勤
# 权重含义：该批次成绩得分率按权重分配到各 CT
BATCH_TYPE_CT_WEIGHTS: dict[int, dict[str, float]] = {
    1: {"CT1": 0.3, "CT2": 0.3, "CT3": 0.2, "CT4": 0.2},
    2: {"CT4": 0.2, "CT5": 0.3, "CT6": 0.3, "CT7": 0.1, "CT8": 0.1},
    3: {"CT1": 0.25, "CT2": 0.25, "CT3": 0.25, "CT4": 0.25},
    4: {"CT1": 0.25, "CT2": 0.25, "CT3": 0.25, "CT4": 0.25},
    5: {"CT7": 0.6, "CT8": 0.4},
}

# 素养类 CT7/CT8 推断权重（无客观题证据，用实践成绩+考勤+参与组合推断）
CT7_LITERACY_WEIGHTS = {"practice": 0.5, "attendance": 0.3, "participation": 0.2}
CT8_LITERACY_WEIGHTS = {"practice": 0.6, "participation": 0.4}

# 达成度等级阈值（OBE 口径，比综合评价 score_to_level 低 5 分）
# ≥85 优秀 / 70-84 良好 / 60-69 合格 / 40-59 不足 / <40 严重不足


def degree_to_level(score: float) -> str:
    """达成度 -> 等级（OBE 达成度口径）。

    比 evaluation.score_to_level 的综合评价阈值低 5 分：
    达成 60% 即算合格达成，达成 85% 算优秀。
    """
    if score >= 85:
        return "优秀"
    if score >= 70:
        return "良好"
    if score >= 60:
        return "合格"
    if score >= 40:
        return "不足"
    return "严重不足"


def parse_ct_field(course_objectives: str | None) -> list[str]:
    """解析知识点 course_objectives 字段为 CT 编号列表。

    输入 "CT1,CT2,CT4" -> ["CT1", "CT2", "CT4"]。
    容错：去空白、过滤空串与非法值、保持顺序去重。
    """
    if not course_objectives:
        return []
    valid = set(CT_CODES)
    seen: set[str] = set()
    out: list[str] = []
    for part in course_objectives.replace(";", ",").replace("，", ",").split(","):
        ct = part.strip().upper()
        if ct in valid and ct not in seen:
            seen.add(ct)
            out.append(ct)
    return out
