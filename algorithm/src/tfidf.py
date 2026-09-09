"""轻量 TF-IDF + 余弦相似度(自包含,纯标准库)。

供 :mod:`verifier` 做语义召回——把大模型输出与各章节考核点做相似度匹配,
判断输出提及的内容是否落在教学大纲考核范围内。

设计与 ``backend/app/services/dedup.py`` 同构(中文按字 + 英文按词),
但不跨服务依赖——algorithm 服务不依赖 backend。
"""
from __future__ import annotations

import math
import re


def tokenize(text: str) -> list[str]:
    """中文按单字 + 英文/数字按词。

    与 backend dedup._tokenize 一致,保证两侧语义检索行为对齐。
    """
    if not text:
        return []
    # 中文字符序列 → 单字
    tokens: list[str] = []
    for seg in re.findall(r"[一-鿿]+", text):
        tokens.extend(list(seg))
    # 英文/数字词
    tokens.extend(w.lower() for w in re.findall(r"[a-zA-Z0-9]+", text))
    return tokens


def build_tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    """计算每篇文档的 TF-IDF 向量(稀疏 dict)。

    参数:
        docs: 每篇文档的分词结果(token 列表)
    返回:
        每篇文档一个 {term: tfidf} 字典
    """
    n = len(docs)
    if n == 0:
        return []
    # DF
    df: dict[str, int] = {}
    for d in docs:
        for term in set(d):
            df[term] = df.get(term, 0) + 1
    # IDF(平滑,避免除零与负值)
    idf = {t: math.log((n + 1) / (cnt + 1)) + 1 for t, cnt in df.items()}

    out: list[dict[str, float]] = []
    for d in docs:
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        total = len(d) or 1
        out.append({t: (c / total) * idf.get(t, 0.0) for t, c in tf.items()})
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """两个稀疏向量的余弦相似度。"""
    if not a or not b:
        return 0.0
    # 遍历较小的一边
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def top_k_similar(query: str, corpus: list[str], top_k: int = 5) -> list[tuple[int, float]]:
    """查询串与语料库各文档的 Top-K 相似度。

    参数:
        query: 查询文本
        corpus: 语料文档列表(原始文本,内部自动分词)
        top_k: 返回条数
    返回:
        [(corpus_index, similarity), ...] 按相似度降序,similarity 四舍五入到 3 位
    """
    if not query.strip() or not corpus:
        return []
    docs = [tokenize(query)] + [tokenize(c) for c in corpus]
    vecs = build_tfidf(docs)
    query_vec = vecs[0]
    scored = [
        (i, round(cosine(query_vec, vecs[i + 1]), 3))
        for i in range(len(corpus))
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
