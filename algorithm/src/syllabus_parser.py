"""教学大纲解析器(小模型验证层的知识源)。

把 ``docs/参考资料/Net教学大纲.docx`` 规则解析成结构化考核点列表,
供 :mod:`verifier` 做考核点对齐验证。

设计要点:
    - 纯函数,不调 LLM,零外部依赖(仅 python-docx,algorithm venv 已装)。
    - 按章节标题正则切分;每章识别「教学目的与要求/教学重点/教学难点/教学内容/学时」
      五个标签,抽成 CheckPoint。
    - 解析失败的章节降级为整章文本块(不阻断,记录 warning),保证 verifier 永远有知识源。
    - 额外抽取课程目标(CT1-CT8)与考核方式,作为补充考核点元数据。

考核点(CheckPoint)结构::

    {
      "chapter": "第一章、计算机网络概论",
      "code": "ch1",
      "objectives": "了解因特网发展...",      # 教学目的与要求
      "key_points": ["因特网组成", ...],      # 教学重点(按、/；/，切分)
      "difficulties": ["分组交换原理", ...],  # 教学难点
      "content": "因特网概述、组成...",       # 教学内容原文
      "content_keywords": [...],              # 教学内容切分的关键词
      "hours": 6,
      "kp_terms": [...],                      # 上述四类合并去重的关键词集
    }
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


# ===== 章节与标签正则 =====
# 「第一章、计算机网络概论」「第1章 计算机网络概论」两种写法都兼容
_CHAPTER_RE = re.compile(r"^第([一二三四五六七八九十\d]+)章[、\s.．]*(.+)$")
# 「教学目的与要求：」「教学重点：」等;冒号兼容中英文
_LABEL_PATTERNS = {
    "objectives": re.compile(r"教学目的与要求[:：](.*)"),
    "key_points": re.compile(r"教学重点[:：](.*)"),
    "difficulties": re.compile(r"教学难点[:：](.*)"),
    "content": re.compile(r"教学内容[:：](.*)"),
    "hours": re.compile(r"学时分配[:：]\s*(\d+)\s*学时"),
}
# 课程目标表里的编号 CT1-CT8
_COURSE_OBJ_RE = re.compile(r"CT\d")
# 切分关键词的分隔符:中文分号/逗号/顿号/句号
_SPLIT_RE = re.compile(r"[；;。.,，、]\s*")


@dataclass
class CheckPoint:
    """一个章节的考核点。"""

    chapter: str
    code: str
    objectives: str = ""
    key_points: list[str] = field(default_factory=list)
    difficulties: list[str] = field(default_factory=list)
    content: str = ""
    content_keywords: list[str] = field(default_factory=list)
    hours: int = 0
    kp_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "code": self.code,
            "objectives": self.objectives,
            "key_points": self.key_points,
            "difficulties": self.difficulties,
            "content": self.content,
            "content_keywords": self.content_keywords,
            "hours": self.hours,
            "kp_terms": self.kp_terms,
        }


def _cn_num_to_int(s: str) -> int:
    """中文数字转 int(支持一到十及组合)。失败回退原数字。"""
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if s.isdigit():
        return int(s)
    if s in cn_map:
        return cn_map[s]
    # 「十一」「二十」等组合(本期大纲只到五,简单兜底)
    if "十" in s:
        parts = s.split("十")
        tens = cn_map.get(parts[0], 1) if parts[0] else 1
        ones = cn_map.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return 0


def _split_terms(text: str) -> list[str]:
    """切分关键词列表,去空白、去重保序。"""
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _extract_paragraphs(path: Path) -> list[str]:
    """用 python-docx 抽取正文段落(保留顺序,去空行)。

    只取段落,不取表格——表格里的「第1章...」是课程目标矩阵/进度表的行,
    不是章节标题,混入会污染章节切分。表格内容由 :func:`parse_course_objectives`
    单独处理。
    """
    from docx import Document  # type: ignore

    doc = Document(str(path))
    lines: list[str] = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            lines.append(t)
    return lines


def parse_syllabus(path: str | Path) -> list[CheckPoint]:
    """解析教学大纲为考核点列表。

    参数:
        path: .docx 大纲文件路径
    返回:
        list[CheckPoint],按章节顺序;解析失败的章节降级为整章文本块。
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"大纲文件不存在,返回空考核点列表: {path}")
        return []

    try:
        lines = _extract_paragraphs(path)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"大纲文本抽取失败: {e}")
        return []

    # 找到所有章节起始行(仅正文段落,表格里的「第1章」不会被误识别)
    chapter_starts: list[tuple[int, str, str, int]] = []  # (line_idx, chapter_title, code, num)
    for i, line in enumerate(lines):
        m = _CHAPTER_RE.match(line)
        if m:
            num_str, title = m.group(1), m.group(2).strip()
            num = _cn_num_to_int(num_str)
            chapter_starts.append((i, line, f"ch{num}", num))

    if not chapter_starts:
        logger.warning("大纲未识别到任何章节标题,返回空列表")
        return []

    checkpoints: list[CheckPoint] = []
    for idx, (start_i, title, code, _num) in enumerate(chapter_starts):
        # 章节文本范围:本章起始行 → 下一章起始行
        end_i = chapter_starts[idx + 1][0] if idx + 1 < len(chapter_starts) else len(lines)
        section_lines = lines[start_i:end_i]

        cp = _parse_chapter(title, code, section_lines)
        checkpoints.append(cp)

    logger.info(f"大纲解析完成: {len(checkpoints)} 个章节考核点")
    return checkpoints


def _parse_chapter(title: str, code: str, section_lines: list[str]) -> CheckPoint:
    """解析单章节文本为 CheckPoint。

    解析失败的标签降级为空;若整个章节都识别不出标签,把章节文本塞进 objectives
    作为兜底(保证 verifier 有内容可比对)。
    """
    cp = CheckPoint(chapter=title, code=code)
    # 把章节内多行拼起来再按标签提取(标签值可能跨行,本期大纲单行足够)
    joined = "\n".join(section_lines)

    for field_name, pattern in _LABEL_PATTERNS.items():
        m = pattern.search(joined)
        if not m:
            continue
        if field_name == "hours":
            cp.hours = int(m.group(1))
        elif field_name == "objectives":
            cp.objectives = m.group(1).strip()
        elif field_name == "content":
            cp.content = m.group(1).strip()
            cp.content_keywords = _split_terms(cp.content)
        elif field_name in ("key_points", "difficulties"):
            terms = _split_terms(m.group(1).strip())
            setattr(cp, field_name, terms)

    # 兜底:整个章节都没识别出任何标签 → 把文本塞进 objectives
    has_any = bool(cp.objectives or cp.key_points or cp.difficulties or cp.content)
    if not has_any:
        logger.warning(f"章节 [{title}] 未识别出考核点标签,降级为整章文本块")
        cp.objectives = " ".join(section_lines[1:])[:500]  # 跳过标题行

    # 合并去重 kp_terms(供 verifier 做关键词匹配与向量化)
    all_terms: list[str] = []
    for src in (cp.key_points, cp.difficulties, cp.content_keywords):
        for t in src:
            if t and t not in all_terms:
                all_terms.append(t)
    # objectives 也切成短句加入(它常含「掌握/理解/了解」动词+知识点)
    if cp.objectives:
        for t in _split_terms(cp.objectives):
            if t and t not in all_terms and len(t) <= 12:
                all_terms.append(t)
    cp.kp_terms = all_terms

    return cp


def parse_course_objectives(path: str | Path) -> list[dict[str, str]]:
    """抽取课程目标表(CT1-CT8)。

    大纲 TABLE 1 里:知识/能力/素养 | CT1 | 描述。
    返回 [{code, category, desc}]。供 verifier 做更细粒度的能力层级校验(可选)。
    """
    path = Path(path)
    if not path.exists():
        return []
    try:
        from docx import Document  # type: ignore

        doc = Document(str(path))
    except Exception:  # noqa: BLE001
        return []

    objs: list[dict[str, str]] = []
    valid_categories = {"知识", "能力", "素养"}
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            # 形如 ['知识', 'CT1', '掌握计算机网络通信技术基本原理...']
            if len(cells) >= 3 and _COURSE_OBJ_RE.match(cells[1]) and cells[0] in valid_categories:
                objs.append({
                    "code": cells[1],
                    "category": cells[0],
                    "desc": cells[2],
                })
    return objs


def parse_assessment(path: str | Path) -> str:
    """抽取考核方式文本(平时30%+实践30%+期末40%)。"""
    path = Path(path)
    if not path.exists():
        return ""
    try:
        lines = _extract_paragraphs(path)
    except Exception:  # noqa: BLE001
        return ""
    # 找「六、考核方式」标题行,取其后到下一节标题前的内容
    for i, line in enumerate(lines):
        if "考核方式" in line:
            chunks: list[str] = []
            for j in range(i, min(i + 5, len(lines))):
                ln = lines[j]
                if j > i and re.match(r"^[七六五六七八九十]+、", ln):
                    break
                chunks.append(ln)
            return "\n".join(chunks)
    return ""
