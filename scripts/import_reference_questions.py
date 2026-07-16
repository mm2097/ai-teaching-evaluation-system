#!/usr/bin/env python3
"""参考资料 PDF/DOC 题目解析入库。

用法：
    # 干跑（只生成 JSON，不入库）
    algorithm/.venv/Scripts/python.exe scripts/import_reference_questions.py \\
        --input "docs/参考资料" --output scripts/output --dry-run

    # 正式入库（确保后端在 8000 端口运行）
    algorithm/.venv/Scripts/python.exe scripts/import_reference_questions.py \\
        --input "docs/参考资料" --output scripts/output \\
        --api-base http://localhost:8000 --batch-size 5

处理流程：
    PDF/DOC → 文本抽取 → 按题号切片 → 批量喂 LLM 结构化（每批 batch_size 题）
    → _check_single 业务校验 → classifier 按关键词分配 courseId
    → dry-run 写 JSON / 正式跑调 HTTP import-rows
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from loguru import logger

# 确保 scripts/ 在 sys.path 中（使同级模块可导入）
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from classifier import classify, course_name  # noqa: E402
from importer import import_questions, write_dry_run_output  # noqa: E402
from llm_structure import structure_batch  # noqa: E402
from parsers.doc_parser import extract_doc_text  # noqa: E402
from parsers.pdf_parser import extract_pdf_text  # noqa: E402
from parsers.splitter import split_questions  # noqa: E402


# 两份网络 DOC 强制归 courseId=1（不进分类器）
_NETWORK_FILE_KEYWORDS = ["网络"]
# 答案区参考文本的最大长度（超过则截断，控制 token）
_MAX_ANSWER_REF_CHARS = 2000
# 单题文本最大长度（超过则跳过，防止超大块拖慢 LLM）
_MAX_CHUNK_CHARS = 3000


def _find_files(input_path: str) -> list[Path]:
    """查找 input_path 下所有 PDF/DOC/DOCX 文件。"""
    root = Path(input_path)
    if not root.exists():
        raise FileNotFoundError(f"输入路径不存在：{root}")

    files: list[Path] = []
    if root.is_file():
        files = [root]
    else:
        for ext in ("*.pdf", "*.PDF", "*.doc", "*.DOC", "*.docx", "*.DOCX"):
            files.extend(root.rglob(ext))

    # 去重 + 排序
    seen = set()
    unique = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    unique.sort()
    return unique


def _extract_text(file_path: Path) -> str:
    """根据文件后缀选择解析器。"""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(file_path)
    elif suffix in (".doc", ".docx"):
        return extract_doc_text(file_path)
    else:
        raise ValueError(f"不支持的文件格式：{suffix}")


def _is_forced_network(file_path: Path) -> int | None:
    """判断是否为网络专题文件（强制 courseId=1）。"""
    name = file_path.name
    for kw in _NETWORK_FILE_KEYWORDS:
        if kw in name:
            return 1
    return None


def _batched(items: list, size: int):
    """把列表切成固定大小的批次。"""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def process_file(
    file_path: Path,
    batch_size: int,
    forced_course: int | None,
) -> tuple[list[dict], list[dict]]:
    """处理单个文件，返回 (合格题目列表, 跳过题目列表)。

    每道题 dict 含完整字段 + courseId + sourceFile。
    """
    logger.info(f"{'='*60}")
    logger.info(f"处理文件：{file_path.name}")

    # 1. 抽取文本
    try:
        text = _extract_text(file_path)
    except Exception as e:  # noqa: BLE001
        logger.error(f"文本抽取失败：{e}")
        return [], [{"sourceFile": file_path.name, "reason": f"文本抽取失败：{e}"}]

    logger.info(f"抽取文本 {len(text)} 字符")
    if len(text) < 50:
        logger.warning("文本过短，可能抽取失败，跳过")
        return [], [{"sourceFile": file_path.name, "reason": "文本过短"}]

    # 2. 切片 + 分离答案区
    chunks, answer_ref = split_questions(text)
    if not chunks:
        logger.warning("未切分出任何题目")
        return [], [{"sourceFile": file_path.name, "reason": "未切分出题目"}]

    # 答案参考截断（控制 token）
    if len(answer_ref) > _MAX_ANSWER_REF_CHARS:
        answer_ref = answer_ref[:_MAX_ANSWER_REF_CHARS]
        logger.info(f"答案参考截断到 {_MAX_ANSWER_REF_CHARS} 字符")

    # 3. 批量 LLM 结构化
    all_valid: list[dict] = []
    all_skipped: list[dict] = []

    for batch_idx, batch in enumerate(_batched(chunks, batch_size)):
        nums = [num for num, _ in batch]
        texts = [t for _, t in batch]

        # 拼装批次原始文本
        raw_text = "\n\n".join(texts)

        # 超大块保护
        if len(raw_text) > _MAX_CHUNK_CHARS * batch_size:
            logger.warning(f"批次 {batch_idx} 文本过长（{len(raw_text)} 字符），逐题处理")
            raw_text_per_item = True
        else:
            raw_text_per_item = False

        batch_info = (
            f"来自《{file_path.name}》，题号 {nums[0]}"
            + (f"~{nums[-1]}" if len(nums) > 1 else "")
            + f"，本批次 {len(batch)} 题"
        )

        if raw_text_per_item:
            # 逐题调用
            for num, text_single in batch:
                try:
                    qs = structure_batch(
                        text_single,
                        answer_reference=answer_ref,
                        batch_info=f"来自《{file_path.name}》，题号 {num}",
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"LLM 调用失败（题号 {num}）：{e}")
                    all_skipped.append({"sourceFile": file_path.name, "reason": f"LLM 调用失败：{e}", "text": text_single[:200]})
                    continue
                for q in qs:
                    q["sourceFile"] = file_path.name
                    q["sourceQuestionNumber"] = num
        else:
            try:
                qs = structure_batch(
                    raw_text,
                    answer_reference=answer_ref,
                    batch_info=batch_info,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"LLM 调用失败（批次 {batch_idx}）：{e}")
                for num, text_single in batch:
                    all_skipped.append({
                        "sourceFile": file_path.name,
                        "reason": f"LLM 调用失败：{e}",
                        "text": text_single[:200],
                    })
                continue

            for q in qs:
                q["sourceFile"] = file_path.name

        # 4. 课程分类 + 收集
        for q in qs:
            if forced_course is not None:
                q["courseId"] = forced_course
                reason = f"强制归 {course_name(forced_course)}（文件名含「网络」）"
            else:
                # 用题干+知识点+选项文本做分类
                classify_text = q["stem"]
                if q.get("knowledgePoint"):
                    classify_text += " " + q["knowledgePoint"]
                if q.get("options"):
                    classify_text += " " + " ".join(
                        o.get("text", "") for o in q["options"] if isinstance(o, dict)
                    )
                cid, reason = classify(classify_text)
                q["courseId"] = cid

            if q["courseId"] is None:
                q["skipReason"] = reason
                all_skipped.append(q)
                logger.debug(f"  跳过题号 {q.get('sourceQuestionNumber', '?')}：{reason}")
            else:
                all_valid.append(q)
                logger.debug(
                    f"  ✓ 题号 {q.get('sourceQuestionNumber', '?')} → "
                    f"{course_name(q['courseId'])} [{q['type']}] {q['stem'][:40]}"
                )

        # 批次间小憩（防限速）
        time.sleep(0.5)

    logger.info(
        f"文件 {file_path.name} 完成：合格 {len(all_valid)} 题，跳过 {len(all_skipped)} 题"
    )
    return all_valid, all_skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="参考资料 PDF/DOC 题目解析入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", required=True,
        help="输入目录或文件路径（如 docs/参考资料）",
    )
    parser.add_argument(
        "--output", default="scripts/output",
        help="输出目录（dry-run JSON / 日志）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只生成 JSON 不入库",
    )
    parser.add_argument(
        "--api-base", default="http://localhost:8000",
        help="后端 API 地址（默认 http://localhost:8000）",
    )
    parser.add_argument(
        "--batch-size", type=int, default=5,
        help="每批 LLM 结构化的题目数（默认 5）",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        help="日志级别（DEBUG/INFO/WARNING/ERROR）",
    )
    args = parser.parse_args()

    # 日志配置
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)
    logger.add(
        log_dir / f"parse_{time.strftime('%Y%m%d_%H%M%S')}.log",
        level="DEBUG",
        encoding="utf-8",
    )

    logger.info(f"配置：input={args.input}, dry_run={args.dry_run}, batch_size={args.batch_size}")

    # 1. 查找文件
    files = _find_files(args.input)
    logger.info(f"找到 {len(files)} 个文件：{[f.name for f in files]}")
    if not files:
        return

    # 2. 逐文件处理
    all_valid: list[dict] = []
    all_skipped: list[dict] = []

    for file_path in files:
        forced = _is_forced_network(file_path)
        if forced:
            logger.info(f"文件 {file_path.name} 含「网络」，强制 courseId=1")
        valid, skipped = process_file(file_path, args.batch_size, forced)
        all_valid.extend(valid)
        all_skipped.extend(skipped)

    # 3. 汇总
    logger.info(f"{'='*60}")
    logger.info(f"全部完成：合格 {len(all_valid)} 题，跳过 {len(all_skipped)} 题")

    # 按课程统计
    from collections import Counter
    cid_counts = Counter(q.get("courseId") for q in all_valid)
    for cid, cnt in sorted(cid_counts.items(), key=lambda x: (x[0] or 0)):
        logger.info(f"  {course_name(cid)}：{cnt} 题")

    if all_skipped:
        skip_reasons = Counter()
        for s in all_skipped:
            skip_reasons[s.get("skipReason", s.get("reason", "未知"))] += 1
        logger.info("跳过原因统计：")
        for reason, cnt in skip_reasons.most_common():
            logger.info(f"  [{cnt}题] {reason[:60]}")

    # 4. 输出
    if args.dry_run:
        write_dry_run_output(output_dir, all_valid, all_skipped)
        logger.info(f"干跑完成，JSON 已写入 {output_dir}，请检查后去掉 --dry-run 正式入库")
    else:
        if not all_valid:
            logger.warning("没有合格题目可入库")
            return
        results = import_questions(args.api_base, all_valid)
        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_skipped = sum(r.get("skipped", 0) for r in results.values())
        logger.info(f"入库完成：导入 {total_imported} 题，跳过(重复) {total_skipped} 题")

        # 入库后建议重建向量索引
        logger.info("提示：入库后可调 POST /api/v1/vector/rebuild 全量重建向量索引")


if __name__ == "__main__":
    main()
