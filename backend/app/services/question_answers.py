"""题目标准答案的兼容编码、展示与客观题判定。"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable

_FILL_BLANK_TYPES = {4, "fill_blank"}
_MULTI_CHOICE_TYPES = {2, "multi_choice"}
_TRUE_VALUES = {"1", "true", "yes", "正确", "对", "是"}
_FALSE_VALUES = {"0", "false", "no", "错误", "错", "否"}


def decode_answer_list(raw_answer: str | None) -> list[str]:
    """读取 JSON 新格式与逗号/顿号分隔的旧格式。"""
    raw = (raw_answer or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return _clean_values(parsed)
    if re.search(r"[,，、|]", raw):
        return _clean_values(re.split(r"[,，、|]", raw))
    return [raw]


def encode_correct_answer(
    question_type: int | str,
    answer: str,
    answer_list: Iterable[str] | None = None,
) -> str:
    """多答案填空题使用 JSON，其他题型保持紧凑字符串。"""
    values = _clean_values(answer_list or [])
    if question_type in _FILL_BLANK_TYPES and values:
        return json.dumps(values, ensure_ascii=False)
    if question_type in _MULTI_CHOICE_TYPES and values:
        return "".join(values)
    return (answer or "").strip()


def answer_for_response(question_type: int | str, stored_answer: str) -> tuple[str, list[str] | None]:
    """将数据库答案转换为前端 answer/answerList。"""
    if question_type in _FILL_BLANK_TYPES:
        values = decode_answer_list(stored_answer)
        return (values[0] if values else "", values or None)
    if question_type in _MULTI_CHOICE_TYPES and stored_answer.strip().startswith("["):
        return "".join(decode_answer_list(stored_answer)), None
    return stored_answer, None


def is_answer_provided(question_type: int | str, user_answer: str | None) -> bool:
    """判断学生是否已作答（空串、纯空白、无效判断题答案视为未答）。"""
    if user_answer is None:
        return False
    text = str(user_answer).strip()
    if not text:
        return False
    if question_type in (3, "judge"):
        return _truth_value(text) is not None
    return True


def judge_objective_answer(question_type: int, correct_answer: str, user_answer: str) -> bool:
    """安全判定四类客观题，无法识别的判断题答案一律判错。"""
    correct = (correct_answer or "").strip()
    user = (user_answer or "").strip()
    if not user:
        return False

    if question_type == 1:
        return user.upper() == correct.upper()
    if question_type == 2:
        correct_choices = _choice_set(correct)
        user_choices = _choice_set(user)
        return bool(correct_choices) and correct_choices == user_choices
    if question_type == 3:
        correct_value = _truth_value(correct)
        user_value = _truth_value(user)
        return correct_value is not None and user_value is not None and correct_value == user_value
    if question_type == 4:
        normalized_user = _normalize_text(user)
        return any(
            _normalize_text(accepted) == normalized_user
            for accepted in decode_answer_list(correct)
        )
    return False


def _clean_values(values: Iterable[object]) -> list[str]:
    return [text for value in values if (text := str(value).strip())]


def _choice_set(raw: str) -> set[str]:
    values = decode_answer_list(raw) if raw.startswith("[") else [raw]
    return {
        character.upper()
        for value in values
        for character in re.findall(r"[A-Za-z0-9]", value)
    }


def _truth_value(raw: str) -> bool | None:
    value = _normalize_text(raw)
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return None


def _normalize_text(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip()).casefold()
