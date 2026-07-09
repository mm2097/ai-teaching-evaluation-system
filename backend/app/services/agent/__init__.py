"""Agent 智能体层。

模块（对应 AI_Agent_设计方案.md）：
    base.py          FC 循环内核
    memory.py        会话记忆
    llm_proxy.py     调 algorithm 8001 的 HTTP 网关
    registry.py      工具注册表（name → callable + schema）
    tools/           工具实现
        queries.py   Agent A 学情查询（10 个）
        exam.py      Agent B 组卷
    prompts/         系统指令
        qa.py        Agent A
        exam.py      Agent B
"""
