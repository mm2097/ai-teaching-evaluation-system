"""Agent Function Calling 循环内核。

核心循环（最多 max_steps 步）：
    [1] 组装 messages（system + 历史 + 当前）→ 调 LLM
    [2] 若 LLM 请求 tool_calls → 执行工具 → 结果回灌 messages → 回 [1]
    [3] 若 LLM 直接输出 content → 循环结束，返回最终答案

过程可观测：每步产出 AgentStep，含 tool_calls、tool_results、content。
失败兜底：步数超限、LLM 异常、工具异常均有降级文本。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Iterator

from loguru import logger

from app.services.agent.llm_proxy import FCResult, get_llm_proxy
from app.services.agent.memory import Conversation, get_or_create_session
from app.services.agent.prompts import (
    EXAM_SYSTEM_PROMPT,
    QA_SYSTEM_PROMPT,
    TUTOR_SYSTEM_PROMPT,
)
from app.services.agent.registry import ToolContext, ToolRegistry, get_registry
from app.services.agent.tools import register_all_tools


# ===== 启动时注册全部工具 =====
_registered = False


def _ensure_tools_registered() -> None:
    global _registered
    if not _registered:
        register_all_tools()
        _registered = True


def _resolve_agent_setup(agent_type: str, registry: ToolRegistry, allow_mutation: bool):
    """按 agent_type 解析 (系统提示词, 可用工具 schema)。

    - exam  ：组卷 Agent，教师侧，挂载全部工具
    - tutor ：学生助学 Agent，只给提示不给答案，**不挂载任何工具**
              （学情查询工具会读班级/他人数据，学生侧一律不提供，从机制上杜绝越权）
    - 其它  ：默认 qa 学情问答（教师侧），挂载全部工具
    """
    if agent_type == "exam":
        return EXAM_SYSTEM_PROMPT, registry.to_openai_schemas(
            agent="both", include_mutation=allow_mutation
        )
    if agent_type == "tutor":
        return TUTOR_SYSTEM_PROMPT, []
    return QA_SYSTEM_PROMPT, registry.to_openai_schemas(
        agent="both", include_mutation=allow_mutation
    )


# ===== 数据结构 =====

@dataclass
class ToolCallRecord:
    """单次工具调用记录（供前端展示过程）。"""

    name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None
    elapsed_ms: int = 0


@dataclass
class AgentStep:
    """Agent 单步记录。"""

    step: int
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    content: str = ""           # LLM 文本输出（最后一步才有）
    finish_reason: str = "stop"
    elapsed_ms: int = 0


@dataclass
class AgentResult:
    """Agent 完整执行结果。"""

    answer: str                         # 最终文本答案
    steps: list[AgentStep] = field(default_factory=list)
    total_elapsed_ms: int = 0
    total_tokens: int = 0
    truncated: bool = False             # 是否因步数上限截断
    error: str | None = None            # 异常时的降级说明

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "steps": [
                {
                    "step": s.step,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "error": tc.error,
                            "elapsed_ms": tc.elapsed_ms,
                        }
                        for tc in s.tool_calls
                    ],
                    "content": s.content,
                    "elapsed_ms": s.elapsed_ms,
                }
                for s in self.steps
            ],
            "total_elapsed_ms": self.total_elapsed_ms,
            "total_tokens": self.total_tokens,
            "truncated": self.truncated,
            "error": self.error,
        }


# ===== 主循环 =====

def run_agent(
    session_factory,          # () -> Session（每次调用新建）
    user_message: str,
    user_id: int,
    course_id: int | None = None,
    student_id: int | None = None,
    session_id: str | None = None,
    agent_type: str = "qa",   # qa / exam
    max_steps: int = 5,
    allow_mutation: bool = False,
    llm_proxy=None,           # 注入用于测试
) -> AgentResult:
    """同步执行 Agent 循环（非流式）。

    session_factory: 产生 SQLModel Session 的工厂（每次调用新建一个）
    返回 AgentResult，含完整步骤记录。
    """
    _ensure_tools_registered()
    start = time.perf_counter()

    proxy = llm_proxy or get_llm_proxy()
    registry = get_registry()
    system_prompt, tool_schemas = _resolve_agent_setup(agent_type, registry, allow_mutation)

    # 会话记忆
    sid = session_id or f"u{user_id}_c{course_id or 0}_default"
    conv = get_or_create_session(sid, user_id, course_id, student_id)
    conv.add_user(user_message)

    # 组装 messages
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(conv.recent_messages(max_rounds=6))

    steps: list[AgentStep] = []
    total_tokens = 0
    truncated = False
    error = None

    try:
        for step_idx in range(1, max_steps + 1):
            step_start = time.perf_counter()
            step = AgentStep(step=step_idx)

            # 调 LLM
            try:
                fc: FCResult = proxy.chat_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"Agent 第 {step_idx} 步 LLM 调用失败：{e}")
                error = f"LLM 服务暂不可用：{e}"
                break

            total_tokens += fc.input_tokens + fc.output_tokens
            step.finish_reason = fc.finish_reason

            # 无工具调用 → 最终答案
            if not fc.tool_calls:
                step.content = fc.content
                steps.append(step)
                break

            # 有工具调用 → 执行并把结果回灌
            # 先记录 assistant 的 tool_calls 到 messages
            assistant_msg: dict = {
                "role": "assistant",
                "content": fc.content or "",
            }
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(fc.tool_calls)
            ]
            messages.append(assistant_msg)

            # 执行每个工具
            for tc in fc.tool_calls:
                tc_record = ToolCallRecord(
                    name=tc["name"],
                    arguments=tc.get("arguments", {}),
                )
                tc_start = time.perf_counter()
                try:
                    result = _execute_tool(
                        registry=registry,
                        session_factory=session_factory,
                        user_id=user_id,
                        course_id=course_id,
                        student_id=student_id,
                        allow_mutation=allow_mutation,
                        name=tc["name"],
                        arguments=tc.get("arguments", {}),
                    )
                    tc_record.result = result
                except Exception as e:  # noqa: BLE001
                    tc_record.error = f"{type(e).__name__}: {e}"
                    result = {"error": tc_record.error}

                tc_record.elapsed_ms = int((time.perf_counter() - tc_start) * 1000)
                step.tool_calls.append(tc_record)

                # 回灌 tool 结果到 messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_0"),
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:4000],
                })

            step.elapsed_ms = int((time.perf_counter() - step_start) * 1000)
            steps.append(step)

            # 到达步数上限
            if step_idx >= max_steps:
                truncated = True
                break

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Agent 循环未预期异常：{e}")
        error = str(e)

    # 最终答案
    final_answer = ""
    if steps and steps[-1].content:
        final_answer = steps[-1].content
    elif error:
        final_answer = f"抱歉，处理您的问题时遇到困难：{error}。请稍后重试或换一种问法。"
    elif truncated:
        final_answer = "已达到最大推理步数，基于现有数据给出上述分析。如需更深入的分析，请追问具体问题。"

    # 记录 assistant 最终回复到会话
    if final_answer:
        conv.add_assistant(
            content=final_answer,
            tool_calls=[
                {"name": tc.name, "arguments": tc.arguments, "id": f"call_{i}"}
                for s in steps for i, tc in enumerate(s.tool_calls)
            ] if False else [],  # tool_calls 已在 recent_messages 中展开，这里简化
        )

    total_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        f"Agent 完成 steps={len(steps)} tokens={total_tokens} "
        f"elapsed={total_ms}ms truncated={truncated}"
    )

    return AgentResult(
        answer=final_answer,
        steps=steps,
        total_elapsed_ms=total_ms,
        total_tokens=total_tokens,
        truncated=truncated,
        error=error,
    )


def _execute_tool(
    registry: ToolRegistry,
    session_factory,
    user_id: int,
    course_id: int | None,
    student_id: int | None,
    allow_mutation: bool,
    name: str,
    arguments: dict,
) -> dict:
    """执行单个工具调用（独立 session，执行完即关）。"""
    session = session_factory()
    try:
        ctx = ToolContext(
            session=session,
            user_id=user_id,
            course_id=course_id,
            student_id=student_id,
            allow_mutation=allow_mutation,
        )
        return registry.execute(name, ctx, arguments)
    finally:
        session.close()


# ===== 流式版本（SSE 用） =====

def run_agent_stream(
    session_factory,
    user_message: str,
    user_id: int,
    course_id: int | None = None,
    student_id: int | None = None,
    session_id: str | None = None,
    agent_type: str = "qa",
    max_steps: int = 5,
    allow_mutation: bool = False,
    llm_proxy=None,
) -> Iterator[dict]:
    """流式版 Agent：yield 每个事件供 SSE 推送。

    事件类型：
        {"type": "step_start", "step": N}
        {"type": "tool_call", "step": N, "name": ..., "arguments": ...}
        {"type": "tool_result", "step": N, "name": ..., "result": ..., "elapsed_ms": ...}
        {"type": "content", "step": N, "content": ...}
        {"type": "done", "total_elapsed_ms": ..., "total_tokens": ..., "truncated": ...}
        {"type": "error", "message": ...}
    """
    _ensure_tools_registered()
    start = time.perf_counter()

    proxy = llm_proxy or get_llm_proxy()
    registry = get_registry()
    system_prompt, tool_schemas = _resolve_agent_setup(agent_type, registry, allow_mutation)

    sid = session_id or f"u{user_id}_c{course_id or 0}_default"
    conv = get_or_create_session(sid, user_id, course_id, student_id)
    conv.add_user(user_message)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(conv.recent_messages(max_rounds=6))

    total_tokens = 0
    truncated = False
    final_answer = ""

    try:
        for step_idx in range(1, max_steps + 1):
            yield {"type": "step_start", "step": step_idx}

            try:
                fc = proxy.chat_with_tools(messages, tool_schemas, "auto")
            except Exception as e:  # noqa: BLE001
                yield {"type": "error", "message": f"LLM 服务暂不可用：{e}"}
                return

            total_tokens += fc.input_tokens + fc.output_tokens

            if not fc.tool_calls:
                final_answer = fc.content
                yield {"type": "content", "step": step_idx, "content": fc.content}
                break

            # 记录 assistant tool_calls
            assistant_msg = {"role": "assistant", "content": fc.content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                    },
                }
                for i, tc in enumerate(fc.tool_calls)
            ]
            messages.append(assistant_msg)

            for tc in fc.tool_calls:
                tc_start = time.perf_counter()
                yield {
                    "type": "tool_call",
                    "step": step_idx,
                    "name": tc["name"],
                    "arguments": tc.get("arguments", {}),
                }
                result = _execute_tool(
                    registry, session_factory, user_id, course_id, student_id,
                    allow_mutation, tc["name"], tc.get("arguments", {}),
                )
                elapsed_ms = int((time.perf_counter() - tc_start) * 1000)
                yield {
                    "type": "tool_result",
                    "step": step_idx,
                    "name": tc["name"],
                    "result": result,
                    "elapsed_ms": elapsed_ms,
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_0"),
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:4000],
                })

            if step_idx >= max_steps:
                truncated = True
                break

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Agent 流式异常：{e}")
        yield {"type": "error", "message": str(e)}
        return

    if final_answer:
        conv.add_assistant(content=final_answer)

    yield {
        "type": "done",
        "total_elapsed_ms": int((time.perf_counter() - start) * 1000),
        "total_tokens": total_tokens,
        "truncated": truncated,
        "answer": final_answer,
    }
