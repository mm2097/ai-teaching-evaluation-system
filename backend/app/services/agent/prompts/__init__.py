"""Agent 系统指令（prompts）。

按 Agent 类型加载：
    qa    Agent A 学情问答
    exam  Agent B 组卷
"""
from .qa import QA_SYSTEM_PROMPT
from .exam import EXAM_SYSTEM_PROMPT

__all__ = ["QA_SYSTEM_PROMPT", "EXAM_SYSTEM_PROMPT"]
