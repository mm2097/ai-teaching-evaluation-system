"""Agent 系统指令（prompts）。

按 Agent 类型加载：
    qa        Agent A 学情问答（被动问答）
    exam      Agent B 组卷（RAG 出题）
    tutor     学生助学（只给提示不给答案）
    diagnosis AI 学情诊断（主动编排工具，输出结构化 JSON 诊断报告）
"""
from .qa import QA_SYSTEM_PROMPT
from .exam import EXAM_SYSTEM_PROMPT
from .tutor import TUTOR_SYSTEM_PROMPT
from .diagnosis import DIAGNOSIS_SYSTEM_PROMPT

__all__ = [
    "QA_SYSTEM_PROMPT",
    "EXAM_SYSTEM_PROMPT",
    "TUTOR_SYSTEM_PROMPT",
    "DIAGNOSIS_SYSTEM_PROMPT",
]
