"""调 algorithm/src/llm_client 把文本切片结构化为标准题目 JSON。

复用：
- algorithm/src/llm_client.py 的 get_llm_client()
- algorithm/src/generator.py 的 _parse_json + _check_single
- algorithm/src/schemas.py 的 QuestionSchema / OptionSchema
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# 把 algorithm/ 加入 sys.path，以便复用算法服务的模块
_ALGORITHM_DIR = Path(__file__).resolve().parent.parent / "algorithm"
if str(_ALGORITHM_DIR) not in sys.path:
    sys.path.insert(0, str(_ALGORITHM_DIR))

# 显式加载 algorithm/.env（pydantic_settings 默认从 CWD 读 .env，脚本从项目根运行时找不到）
_env_path = _ALGORITHM_DIR / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path, override=True)

# 复用算法服务已有模块
from src.generator import _check_single, _parse_json  # noqa: E402
from src.llm_client import get_llm_client  # noqa: E402
from src.schemas import OptionSchema, QuestionSchema  # noqa: E402

from prompts import SYSTEM_PROMPT, build_user_prompt


def _to_question_schema(item: dict) -> tuple[QuestionSchema | None, str]:
    """把 LLM 输出的 dict 转成 QuestionSchema 并校验。

    返回：(schema 或 None, 失败原因)
    """
    try:
        # 选项转换
        options = None
        opts = item.get("options")
        if opts and isinstance(opts, list):
            options = [
                OptionSchema(key=str(o.get("key", "")).upper(), text=str(o.get("text", "")))
                for o in opts
            ]

        # answerList 兼容
        answer_list = item.get("answerList") or item.get("answer_list")

        q = QuestionSchema(
            type=item.get("type", "short_answer"),
            stem=item.get("stem", ""),
            options=options,
            answer=str(item.get("answer", "")),
            answer_list=answer_list if isinstance(answer_list, list) else None,
            explanation=item.get("explanation", ""),
            knowledge_point=item.get("knowledgePoint") or item.get("knowledge_point") or "综合",
            difficulty=item.get("difficulty", "medium"),
        )
        return q, ""
    except Exception as e:  # noqa: BLE001
        return None, f"Schema 构建失败：{e}"


def structure_batch(
    raw_text: str,
    answer_reference: str = "",
    batch_info: str = "",
) -> list[dict]:
    """把一批原始题目文本结构化为标准题目 dict 列表。

    参数：
        raw_text: 一批题目的原始文本（1-5 道）
        answer_reference: 答案区参考文本（可选）
        batch_info: 批次说明

    返回：
        合格的题目 dict 列表（每项含 type/stem/options/answer/answerList/
        explanation/knowledgePoint/difficulty/sourceQuestionNumber）
    """
    client = get_llm_client()
    user_prompt = build_user_prompt(raw_text, answer_reference, batch_info)

    result = client.chat_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_mode=True,
    )

    parsed = _parse_json(result.content)
    if parsed is None:
        logger.warning(f"LLM 输出 JSON 解析失败（batch={batch_info}），原始内容前200字：{result.content[:200]}")
        return []

    # 兼容 {"questions": [...]} 或 [...] 两种格式
    if isinstance(parsed, dict) and "questions" in parsed:
        items = parsed["questions"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        logger.warning(f"LLM 输出格式非预期：{type(parsed)}")
        return []

    valid: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        q, err = _to_question_schema(item)
        if q is None:
            logger.warning(f"题目结构化失败：{err} | item={str(item)[:100]}")
            continue

        # 复用 _check_single 做业务校验（required_kps 为空集，不限制知识点）
        ok, reason = _check_single(q, set())
        if not ok:
            logger.warning(f"题目业务校验失败：{reason} | 题干={q.stem[:40]}")
            continue

        # 转回 dict（供 importer / dry-run 输出）
        valid.append({
            "type": q.type,
            "stem": q.stem,
            "options": [{"key": o.key, "text": o.text} for o in q.options] if q.options else None,
            "answer": q.answer,
            "answerList": q.answer_list,
            "explanation": q.explanation,
            "knowledgePoint": q.knowledge_point,
            "difficulty": q.difficulty,
            "sourceQuestionNumber": str(item.get("sourceQuestionNumber", "")),
        })

    logger.info(f"批次结构化完成：输入 {len(items)} 题 → 合格 {len(valid)} 题")
    return valid
