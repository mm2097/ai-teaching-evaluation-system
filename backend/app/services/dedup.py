"""D12 题目去重（TF-IDF + 余弦相似度）。

纯标准库实现，不引入 numpy/sklearn。
- 把题干 + 选项拼接为文档
- 计算 TF-IDF 向量
- 余弦相似度 > 阈值 (默认 0.8) 视为重复
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass
class DedupResult:
    kept: list           # 保留的题目（含原索引）
    duplicates: list     # 被剔除的题目 [{index, dup_of, similarity}]
    threshold: float


def _tokenize(text: str) -> list[str]:
    """中文按字 + 英文按词。"""
    if not text:
        return []
    # 提取中文字符序列
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    tokens: list[str] = []
    for seg in cjk:
        tokens.extend(list(seg))  # 单字
    # 英文单词
    en = re.findall(r"[a-zA-Z0-9]+", text)
    tokens.extend(w.lower() for w in en)
    return tokens


def _build_tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    """计算每篇文档的 TF-IDF 向量（稀疏 dict）。"""
    n = len(docs)
    if n == 0:
        return []
    # DF
    df: dict[str, int] = {}
    for d in docs:
        for term in set(d):
            df[term] = df.get(term, 0) + 1
    # IDF（平滑）
    idf = {t: math.log((n + 1) / (cnt + 1)) + 1 for t, cnt in df.items()}

    out: list[dict[str, float]] = []
    for d in docs:
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        total = len(d) or 1
        vec = {t: (c / total) * idf.get(t, 0) for t, c in tf.items()}
        out.append(vec)
    return out


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _question_text(q: dict) -> str:
    """把题目 dict 拼成可比较的文档。"""
    parts = [str(q.get("content", ""))]
    options = q.get("options")
    if isinstance(options, list):
        parts.extend(str(o) for o in options)
    elif isinstance(options, str):
        parts.append(options)
    if q.get("correct_answer"):
        parts.append(str(q["correct_answer"]))
    return " ".join(parts)


def dedup_questions(
    questions: list[dict], threshold: float = 0.8
) -> DedupResult:
    """对题目列表去重。

    questions: [{content, options, correct_answer, ...}, ...]
    返回 DedupResult。kept 内为题目原对象（附带 _orig_index）。
    """
    docs = [_tokenize(_question_text(q)) for q in questions]
    vectors = _build_tfidf(docs)

    kept: list[dict] = []
    duplicates: list[dict] = []
    kept_vecs: list[tuple[int, dict[str, float]]] = []

    for i, q in enumerate(questions):
        dup_of = -1
        max_sim = 0.0
        for j, v in kept_vecs:
            sim = _cosine(vectors[i], v)
            if sim > max_sim:
                max_sim = sim
                if sim >= threshold:
                    dup_of = j
                    break  # 命中一条即可
        if dup_of >= 0:
            duplicates.append({
                "index": i,
                "dup_of": dup_of,
                "similarity": round(max_sim, 3),
                "content": q.get("content", "")[:50],
            })
        else:
            item = dict(q)
            item["_orig_index"] = i
            kept.append(item)
            kept_vecs.append((len(kept) - 1, vectors[i]))

    return DedupResult(kept=kept, duplicates=duplicates, threshold=threshold)


def check_duplicate_against_bank(
    new_q: dict, bank: list[dict], threshold: float = 0.8
) -> tuple[bool, float, int]:
    """检查新题是否与题库重复。返回 (is_dup, similarity, bank_index)。"""
    if not bank:
        return False, 0.0, -1
    docs = [_tokenize(_question_text(new_q))] + [_tokenize(_question_text(q)) for q in bank]
    vecs = _build_tfidf(docs)
    new_vec = vecs[0]
    best_sim = 0.0
    best_idx = -1
    for i in range(1, len(vecs)):
        sim = _cosine(new_vec, vecs[i])
        if sim > best_sim:
            best_sim = sim
            best_idx = i - 1
    return best_sim >= threshold, round(best_sim, 3), best_idx
