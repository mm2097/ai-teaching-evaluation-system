"""工具注册表。

每个工具是一个 Tool 实例：
    - name: 工具名（与 LLM schema 对应）
    - schema: OpenAI Function Calling 的 JSON Schema
    - handler: 可调用对象 (session, user_id, course_id, **kwargs) -> dict

工具分两类：
    - 读类（query）：默认放行
    - 写类（mutation）：默认禁用，需要白名单显式开启
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlmodel import Session


@dataclass
class Tool:
    """工具定义。"""

    name: str
    description: str
    parameters: dict                 # JSON Schema
    handler: Callable[..., Any]      # (session, ctx, **kwargs) -> dict
    category: str = "query"          # query / mutation
    agent: str = "A"                 # A / B / both


@dataclass
class ToolContext:
    """工具执行上下文（每次调用注入）。"""

    session: Session
    user_id: int
    course_id: int | None = None
    student_id: int | None = None
    # 允许的 mutation 工具白名单
    allow_mutation: bool = False


class ToolRegistry:
    """工具注册中心。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具（幂等：重复注册同一名直接覆盖）。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_for_agent(self, agent: str = "A", include_mutation: bool = False) -> list[Tool]:
        """列出某 Agent 可用的工具。"""
        out = []
        for t in self._tools.values():
            if t.agent not in (agent, "both"):
                continue
            if t.category == "mutation" and not include_mutation:
                continue
            out.append(t)
        return out

    def to_openai_schemas(self, agent: str = "A", include_mutation: bool = False) -> list[dict]:
        """转为 OpenAI Function Calling 的 tools 参数。"""
        out = []
        for t in self.list_for_agent(agent, include_mutation):
            out.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            })
        return out

    def execute(self, name: str, ctx: ToolContext, arguments: dict) -> dict:
        """执行一个工具（带权限校验）。"""
        tool = self.get(name)
        if not tool:
            return {"error": f"工具不存在：{name}"}
        if tool.category == "mutation" and not ctx.allow_mutation:
            return {"error": f"工具 {name} 为写操作，当前会话未授权"}
        try:
            return tool.handler(ctx, **arguments)
        except TypeError as e:
            return {"error": f"参数错误：{e}"}
        except Exception as e:  # noqa: BLE001
            return {"error": f"工具执行异常：{type(e).__name__}: {e}"}


# 全局单例
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry


def register_tool(tool: Tool) -> None:
    get_registry().register(tool)
