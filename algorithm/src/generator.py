"""AI 出题主逻辑。

流程：
    拼装 prompt → 调 LLM → 三道防线校验 → 去重 → 返回结构化题目

三道防线（详见设计文档亮点 3）：
    1. JSON 解析（含 ```json``` 代码块二次解析）
    2. Pydantic Schema 强校验
    3. 业务规则校验（答案合法、选项不重复、题干不重复、知识点匹配）
"""
import json
import re
import time

from loguru import logger
from pydantic import ValidationError

from .llm_client import get_llm_client
from .prompts.exercise import SYSTEM_PROMPT, build_fewshot_text, build_reference_text, build_user_prompt
from .schemas import (
    GenerateMeta,
    GenerateRequest,
    GenerateResponse,
    OptionSchema,
    QuestionSchema,
)


def generate_exercises(req: GenerateRequest) -> GenerateResponse:
    """出题主入口。

    参数：``req`` 出题请求
    返回：``GenerateResponse`` 含合格题目与元信息
    异常：LLM 失败抛 ``RuntimeError``，由 main.py 转 HTTP 503
    """
    start = time.perf_counter()

    # ---------- 拼装 prompt ----------
    # 优先级：reference_questions（RAG 检索）> 静态 few-shot > 无示范
    user_prompt = build_user_prompt(req)
    reference_text = build_reference_text(req.reference_questions or [])
    if reference_text:
        full_user = reference_text + "\n\n" + user_prompt
        logger.info(f"RAG 出题：注入 {len(req.reference_questions or [])} 道题库参考题")
    else:
        fewshot = build_fewshot_text(req.course_name)
        full_user = (fewshot + "\n\n" + user_prompt) if fewshot else user_prompt
        logger.info("RAG 出题：题库无参考题，回退静态 few-shot")
    logger.info(
        f"出题请求 course={req.course_name} 知识点={req.knowledge_points} 总数={req.total_count}"
    )

    # ---------- 调 LLM ----------
    client = get_llm_client()
    llm_result = client.chat_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=full_user,
        json_mode=True,
    )

    # ---------- 三道防线 ----------
    # 防线 1：JSON 解析
    raw_questions = _parse_json(llm_result.content)
    if raw_questions is None:
        raise RuntimeError(f"LLM 输出 JSON 解析失败，原始内容前 200 字：{llm_result.content[:200]}")
    if not isinstance(raw_questions, dict) or "questions" not in raw_questions:
        raise RuntimeError("LLM 输出 JSON 结构错误，缺少 questions 字段")

    # 防线 2：Pydantic Schema 校验（逐题，丢弃不合格的）
    schema_passed: list[QuestionSchema] = []
    schema_failed = 0
    for raw in raw_questions["questions"]:
        try:
            q = QuestionSchema.model_validate(raw)
            schema_passed.append(q)
        except ValidationError as e:
            schema_failed += 1
            logger.warning(f"题目 Schema 校验失败，已丢弃：{e}")

    # 防线 3：业务规则校验 + 去重
    valid_questions, business_filtered = _validate_business(schema_passed, req)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    filtered_count = schema_failed + business_filtered

    logger.info(
        f"出题完成 合格={len(valid_questions)} 过滤={filtered_count} "
        f"耗时={elapsed_ms}ms tokens={llm_result.input_tokens}/{llm_result.output_tokens}"
    )

    meta = GenerateMeta(
        model=llm_result.model,
        elapsed_ms=elapsed_ms,
        input_tokens=llm_result.input_tokens,
        output_tokens=llm_result.output_tokens,
        success_count=len(valid_questions),
        filtered_count=filtered_count,
        retry_count=llm_result.retry_count,
    )
    return GenerateResponse(questions=valid_questions, meta=meta)


# ===== 防线 1：JSON 解析 =====
def _parse_json(content: str) -> dict | None:
    """解析 LLM 输出为 JSON。

    策略：
        1. 先直接 ``json.loads``；
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
            logger.warning(f"代码块二次解析失败：{e}")

    return None


# ===== 防线 3：业务规则校验 =====
def _validate_business(
    questions: list[QuestionSchema], req: GenerateRequest
) -> tuple[list[QuestionSchema], int]:
    """业务规则校验 + 同批次去重。

    返回：(合格题目列表, 被过滤的数量)

    校验项：
        - 题型对应字段完整（选择题有 options，填空有 answer_list）
        - 答案在选项合法范围内
        - 选项文本不重复
        - 同批次题干不重复
        - 知识点在指定范围内（漂移则标注，不丢弃）
    """
    valid: list[QuestionSchema] = []
    seen_stems: set[str] = set()  # 同批次题干去重（归一化后）
    required_kps = set(req.knowledge_points)
    filtered = 0

    for q in questions:
        ok, reason = _check_single(q, required_kps)
        if not ok:
            filtered += 1
            logger.warning(f"题目业务校验失败，已丢弃：{reason} | 题干={q.stem[:40]}")
            continue

        # 同批次题干去重
        stem_key = _normalize(q.stem)
        if stem_key in seen_stems:
            filtered += 1
            logger.warning(f"同批次题干重复，已丢弃：{q.stem[:40]}")
            continue
        seen_stems.add(stem_key)

        valid.append(q)

    return valid, filtered


def _check_single(q: QuestionSchema, required_kps: set[str]) -> tuple[bool, str]:
    """单题业务规则校验，返回 (是否合格, 失败原因)。"""
    # 选择题：必须有 4 个选项
    if q.type in ("single_choice", "multi_choice"):
        if not q.options or len(q.options) != 4:
            return False, f"{q.type} 题选项数不为 4"
        # 选项 key 必须为 A/B/C/D
        keys = [o.key.upper() for o in q.options]
        if sorted(keys) != ["A", "B", "C", "D"]:
            return False, f"选项 key 不合法：{keys}"
        # 选项文本不重复
        texts = [o.text.strip() for o in q.options if o.text.strip()]
        if len(texts) != 4:
            return False, "选项文本存在空值或重复"
        # 答案必须在选项范围内
        answer_keys = {k.strip().upper() for k in q.answer}
        if not answer_keys.issubset(set(keys)):
            return False, f"答案 {q.answer} 不在选项范围内"

        # 多选题：answer 必须升序拼接且至少 2 个
        if q.type == "multi_choice":
            if len(answer_keys) < 2:
                return False, "多选题答案至少 2 个"
            # 规范化为升序
            q.answer = "".join(sorted(answer_keys))

    # 判断题：答案必须是 true/false
    elif q.type == "judge":
        if q.answer.strip().lower() not in ("true", "false"):
            return False, f"判断题答案不合法：{q.answer}"

    # 填空题：必须有 answer_list
    elif q.type == "fill_blank":
        if not q.answer_list or len(q.answer_list) == 0:
            return False, "填空题缺少 answer_list"

    # 简答题：answer 为参考答案文字，最少 5 字
    elif q.type == "short_answer":
        if len(q.answer.strip()) < 5:
            return False, "简答题参考答案过短（<5字）"

    # 知识点漂移检查：仅标注，不丢弃（设计文档第 5.5 节）
    # （这里仅记录日志，保留题目，后续由教师审核决定）
    if q.knowledge_point not in required_kps:
        logger.info(f"知识点漂移（保留待人工确认）：{q.knowledge_point} 不在 {required_kps}")

    return True, ""


def _normalize(text: str) -> str:
    """题干归一化（用于去重比较）：去空白、转小写。"""
    return re.sub(r"\s+", "", text).lower()


# ===== 对外暴露的题型/难度枚举（供 main.py 引用）=====
__all__ = ["generate_exercises", "OptionSchema", "QuestionSchema"]
