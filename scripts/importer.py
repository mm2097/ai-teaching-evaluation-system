"""HTTP 入库模块：调后端 /question-bank/import-rows 接口。

按 courseId 分组后，每课程调一次 import-rows。
接口内置 content 完全相等查重 + _sync_vector 向量同步。
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import httpx
from loguru import logger

# import-rows 期望的字段名（snake_case → camelCase 对齐接口）
_IMPORT_FIELDS = {
    "type", "stem", "options", "answer", "answerList",
    "explanation", "knowledgePoint",
}


def _to_import_row(q: dict) -> dict:
    """把解析后的题目 dict 转为 import-rows 接口期望的 row 格式。"""
    return {k: v for k, v in q.items() if k in _IMPORT_FIELDS}


def import_questions(api_base: str, questions: list[dict]) -> dict:
    """按 courseId 分组调 import-rows 入库。

    返回：{courseId: {imported: N, skipped: N}, ...}
    """
    # 按 courseId 分组
    grouped: dict[int, list[dict]] = defaultdict(list)
    for q in questions:
        cid = q.get("courseId")
        if cid is None:
            continue
        grouped[cid].append(_to_import_row(q))

    results: dict[int, dict] = {}
    client = httpx.Client(timeout=60.0)

    try:
        for cid, rows in grouped.items():
            course_name = {1: "计算机网络", 2: "操作系统", 3: "数据结构"}.get(cid, f"课程{cid}")
            logger.info(f"入库 {course_name}（courseId={cid}）：{len(rows)} 题")

            url = f"{api_base.rstrip('/')}/api/v1/question-bank/import-rows"
            resp = client.post(url, json={"courseId": cid, "rows": rows})

            if resp.status_code != 200:
                logger.error(f"入库失败 courseId={cid}：HTTP {resp.status_code} {resp.text[:200]}")
                results[cid] = {"imported": 0, "skipped": 0, "error": resp.text[:200]}
                continue

            data = resp.json()
            results[cid] = data
            logger.info(
                f"  → 导入 {data.get('imported', 0)} 题，跳过 {data.get('skipped', 0)} 题"
            )
    finally:
        client.close()

    return results


def write_dry_run_output(output_dir: str | Path, questions: list[dict], skipped: list[dict]) -> None:
    """把 dry-run 结果写到 output 目录。

    按课程分文件：parsed_course{cid}.json
    跳过的题目：failed.json
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 按课程分组
    grouped: dict[int, list[dict]] = defaultdict(list)
    for q in questions:
        cid = q.get("courseId", 0)
        grouped[cid].append(q)

    course_names = {1: "计算机网络", 2: "操作系统", 3: "数据结构"}
    for cid, qs in grouped.items():
        name = course_names.get(cid, f"课程{cid}")
        path = output_dir / f"parsed_course{cid}_{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            import json
            json.dump(qs, f, ensure_ascii=False, indent=2)
        logger.info(f"写出 {path}：{len(qs)} 题")

    # 跳过的题目
    if skipped:
        path = output_dir / "failed_skipped.json"
        with open(path, "w", encoding="utf-8") as f:
            import json
            json.dump(skipped, f, ensure_ascii=False, indent=2)
        logger.info(f"写出 {path}：{len(skipped)} 题被跳过")
