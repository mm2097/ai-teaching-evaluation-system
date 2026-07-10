"""AI 判题主逻辑。

流程：
    拼装 prompt → 调 LLM → 三道防线校验 → 返回判分结果

三道防线（参照 generator.py 的模式）：
    1. JSON 解析（含 ```json``` 代码块二次解析）
    2. 业务规则校验（分数范围、字段完整性）
    3. 兜底：返回 manual_required 而非抛异常（对齐 TC-B2-08）
"""
import json
import re
import time

from loguru import logger

from .llm_client import get_llm_client
from .prompts.judge import SYSTEM_PROMPT, build_user_prompt
from .schemas import JudgeRequest, JudgeResponse


def judge_answer(req: JudgeRequest) -> JudgeResponse:
    """判题主入口。

    参数：``req`` 判题请求
    返回：``JudgeResponse`` 含判分结果；失败时 flag=manual_required
    """
    start = time.perf_counter()

    # ---------- 拼装 prompt ----------
    user_prompt = build_user_prompt(req)
    logger.info(
        f"判题请求 题干={req.question_stem[:40]}... 满分={req.max_score}"
    )

    # ---------- 调 LLM ----------
    client = get_llm_client()
    llm_result = client.chat_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_mode=True,
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # ---------- 三道防线 ----------
    # 防线 1：JSON 解析
    raw = _parse_json(llm_result.content)
    if raw is None:
        logger.warning(f"判题 JSON 解析失败，返回 manual_required：{llm_result.content[:200]}")
        return _manual_fallback("JSON 解析失败")

    # 防线 2：业务规则校验
    result, error = _validate_judge(raw, req.max_score)
    if error:
        logger.warning(f"判题业务校验失败：{error}")
        return _manual_fallback(error)

    logger.info(
        f"判题完成 得分={result.total_score}/{req.max_score} "
        f"耗时={elapsed_ms}ms"
    )
    return result


# ===== 防线 1：JSON 解析 =====
def _parse_json(content: str) -> dict | None:
    """解析 LLM 输出为 JSON。

    策略：
        1. 先直接 json.loads；
        2. 失败则提取 ```json ... ``` 代码块二次解析；
        3. 仍失败返回 None。
    """
    # 策略 1：直接解析
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass

    # 策略 2：提取代码块
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"判题代码块二次解析失败：{e}")

    return None


# ===== 防线 2：业务规则校验 =====
def _validate_judge(raw: dict, max_score: float) -> tuple[JudgeResponse | None, str | None]:
    """校验判题结果。

    返回：(JudgeResponse, None) 或 (None, 错误原因)
    """
    # total_score 必须存在且为数字
    total_score = raw.get("total_score")
    if total_score is None:
        return None, "缺少 total_score"
    try:
        total_score = float(total_score)
    except (ValueError, TypeError):
        return None, f"total_score 非数字：{total_score}"

    # 分数范围校验
    if total_score < 0 or total_score > max_score:
        # 尝试钳位
        total_score = max(0.0, min(total_score, max_score))
        logger.info(f"判分超出范围，已钳位至 {total_score}")

    # rubric_points 校验（可选但建议有）
    rubric_points = raw.get("rubric_points", [])
    if not isinstance(rubric_points, list):
        rubric_points = []

    # confidence 校验
    confidence = raw.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
            if confidence < 0:
                confidence = 0.0
            elif confidence > 1:
                confidence = 1.0
        except (ValueError, TypeError):
            confidence = None

    reason = str(raw.get("reason", ""))
    if not reason:
        reason = "AI 未提供判分依据"

    result = JudgeResponse(
        total_score=total_score,
        rubric_points=rubric_points,
        confidence=confidence,
        reason=reason,
        flag="normal",
    )
    return result, None


def _manual_fallback(reason: str) -> JudgeResponse:
    """兜底：返回需人工判分的结果（对齐 TC-B2-08）。"""
    return JudgeResponse(
        total_score=None,
        rubric_points=[],
        confidence=None,
        reason=f"AI 判分失败，需人工判分：{reason}",
        flag="manual_required",
    )
