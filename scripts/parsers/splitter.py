"""按题号正则切片 + 答案区分离。

识别常见的中文试卷题号格式，将全文切分为单道题的文本块。
同时检测并分离"参考答案"区，供后续匹配。
"""

from __future__ import annotations

import re

from loguru import logger

# 答案区起始标记
_ANSWER_MARKERS = [
    "参考答案", "答案及解析", "答案解析", "试题答案",
    "参考答案及解析", "答案", "Answer Key", "Solutions",
    "选择题答案", "综合题答案", "正确答案",
]

# 题号正则（行首 + 数字 + .或、 或 (1) （1））
# 注意：408 真题题号从 1 到 47，所以匹配 1-3 位数字
_QUESTION_PATTERN = re.compile(
    r"^[ \t]*("
    r"\d{1,3}\s*[\.．]\s"        # 1.  或  1．
    r"|\d{1,3}\s*[、]\s"           # 1、
    r"|[\(（]\s*\d{1,3}\s*[\)）]\s"  # (1) 或 （1）
    r")",
    re.MULTILINE,
)


def _find_answer_section(text: str) -> tuple[str, str]:
    """分离答案区。

    返回：(题目正文, 答案参考文本)
    如果找不到答案区，答案参考文本为空。
    """
    best_pos = -1
    for marker in _ANSWER_MARKERS:
        # 在行首找标记
        pattern = re.compile(rf"^[ \t]*{re.escape(marker)}", re.MULTILINE)
        match = pattern.search(text)
        if match and (best_pos == -1 or match.start() < best_pos):
            best_pos = match.start()

    if best_pos == -1:
        return text, ""

    question_text = text[:best_pos].strip()
    answer_text = text[best_pos:].strip()
    logger.info(f"检测到答案区，从位置 {best_pos} 分离（答案区长 {len(answer_text)} 字符）")
    return question_text, answer_text


def split_questions(text: str) -> tuple[list[tuple[str, str]], str]:
    """将全文按题号切分为 [(题号, 题目文本), ...]，并返回答案参考文本。

    返回：(chunks, answer_reference)
        chunks: [(question_number, question_text), ...]
        answer_reference: 答案区全文（供 LLM 参考匹配）
    """
    # 1. 分离答案区
    question_text, answer_ref = _find_answer_section(text)

    # 2. 按题号正则切片
    matches = list(_QUESTION_PATTERN.finditer(question_text))

    if len(matches) < 2:
        logger.warning(f"仅匹配到 {len(matches)} 个题号，可能格式不标准，整段作为一道题")
        if matches:
            num = re.search(r"\d{1,3}", matches[0].group(0))
            return [(num.group() if num else "1", question_text.strip())], answer_ref
        return [("0", question_text.strip())], answer_ref

    chunks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        # 提取题号
        num_match = re.search(r"\d{1,3}", m.group(0))
        num = num_match.group() if num_match else str(i + 1)

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(question_text)
        chunk_text = question_text[start:end].strip()

        if len(chunk_text) < 5:
            # 太短的块跳过（可能是噪声）
            continue

        chunks.append((num, chunk_text))

    logger.info(f"切分为 {len(chunks)} 道题")
    return chunks, answer_ref
