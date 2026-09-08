"""小模型验证器(大小模型协同的「小模型」侧)。

大模型(DeepSeek)先产出评语/诊断/判分依据,本模块用**确定性规则 + TF-IDF 语义召回**
做考核点对齐验证,产出校验报告与置信度,克服大模型的「逻辑漂移」与「幻觉生成」。

「小模型」定义:不是另一个 LLM,而是基于教学大纲考核点的规则引擎——
    1. 对齐校验 aligned   ——输出提及的知识点是否落在大纲考核点 key_points/content_keywords
    2. 幻觉校验 hallucinated ——输出提及但不在任何章节考核范围的术语(硬幻觉+软幻觉)
    3. 覆盖校验 coverage  ——该场景应覆盖的考核点中被提及的比例

零额外 LLM token、零延迟翻倍,确定性可复现。

入口:
    verify_against_syllabus(llm_output, context, course_id) -> VerifyReport

设计原则(对齐项目「稳定性优先」):
    - 任何异常都降级为「未验证」报告,不抛错(verify 是增强,非必需)
    - 大纲缺失时走「无大纲降级」:只做 TF-IDF 召回,不判幻觉
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .syllabus_data import checkpoints_for_course


# ===== 场景阈值 =====
# 诊断场景要求覆盖薄弱点对应章节;判题场景不要求覆盖(单题只考一两个点)
_COVERAGE_THRESHOLDS = {"diagnosis": 0.4, "judge": 0.0, "report": 0.3}

# 跨领域强幻觉黑词(与计网大纲明显无关的领域术语)。命中 → 硬幻觉。
# 注:本期只做计网,这些词是计网诊断里出现即可判异常的信号。
_HARD_HALLUCIN_TERMS = [
    "量子", "量子计算", "量子加密", "区块链", "比特币", "加密货币",
    "神经网络", "深度学习", "机器学习", "梯度下降", "反向传播",
    "基因", "蛋白质", "DNA",
    "微分方程", "傅里叶", "张量",
]


@dataclass
class VerifyReport:
    """小模型验证报告。"""

    aligned_kps: list[str] = field(default_factory=list)
    hallucinated_kps: list[str] = field(default_factory=list)
    coverage: float = 0.0
    confidence: float = 0.0
    flag: str = "pass"  # pass / warn / fail / skipped
    notes: str = ""
    matched_chapters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "aligned_kps": self.aligned_kps,
            "hallucinated_kps": self.hallucinated_kps,
            "coverage": round(self.coverage, 3),
            "confidence": round(self.confidence, 3),
            "flag": self.flag,
            "notes": self.notes,
            "matched_chapters": self.matched_chapters,
        }


def verify_against_syllabus(
    llm_output: str,
    context: dict[str, Any] | None = None,
    course_id: int = 1,
    top_k: int = 5,
) -> VerifyReport:
    """小模型验证:大模型输出对齐教学大纲考核点。

    参数:
        llm_output: 大模型产出的文本(评语/诊断JSON/判分依据)
        context: {scene: "diagnosis"|"judge"|"report", question_stem?, weak_points?}
        course_id: 课程 ID(本期固定 1=计网)
        top_k: TF-IDF 召回的章节数
    返回:
        VerifyReport;异常时返回 flag=skipped 的空报告
    """
    context = context or {}
    scene = context.get("scene", "diagnosis")

    # 异常降级:任何报错都不阻断主流程
    try:
        cps = checkpoints_for_course(course_id)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"验证器取考核点失败: {e}")
        return VerifyReport(flag="skipped", notes=f"考核点加载失败: {e}")

    if not cps:
        # 无大纲降级:只做 TF-IDF 召回,无法判对齐/幻觉
        return _verify_no_syllabus(llm_output, scene)

    try:
        return _verify_with_syllabus(llm_output, cps, scene, context, top_k)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"验证器执行异常,降级为 skipped: {e}")
        return VerifyReport(flag="skipped", notes=f"验证异常: {e}")


# ===== 有大纲的完整验证 =====

def _verify_with_syllabus(
    llm_output: str,
    cps: list,
    scene: str,
    context: dict[str, Any],
    top_k: int,
) -> VerifyReport:
    """有大纲的三项校验。"""
    text = llm_output or ""

    # --- 1. 对齐校验:输出里出现了哪些大纲关键词 ---
    aligned: list[str] = []
    matched_chapters: set[str] = set()
    for cp in cps:
        for term in cp.kp_terms:
            if term and term in text and term not in aligned:
                aligned.append(term)
                matched_chapters.add(cp.code)

    # --- 2. 幻觉校验 ---
    hallucinated: list[str] = []
    notes_parts: list[str] = []

    # 2a. 硬幻觉:跨领域黑词
    for bad in _HARD_HALLUCIN_TERMS:
        if bad in text and bad not in hallucinated:
            hallucinated.append(bad)
    if hallucinated:
        notes_parts.append(f"输出提及跨领域术语 {hallucinated} 不在计网大纲考核范围")

    # 2b. 软幻觉:输出里的专有名词短语既非大纲关键词、TF-IDF 与所有章节都低相似
    soft = _detect_soft_hallucinations(text, cps)
    if soft:
        # 软幻觉只记 notes,不进 hallucinated_kps(避免误杀同义表述)
        notes_parts.append(f"疑似超纲表述: {soft[:5]}")

    # --- 3. 覆盖校验 ---
    # 应覆盖的章节集合:诊断用 weak_points 对应章节,无则全部;判题用题干对应章节
    expected_chapters = _expected_chapters(scene, context, cps, text)
    if expected_chapters:
        covered = matched_chapters & expected_chapters
        coverage = len(covered) / len(expected_chapters) if expected_chapters else 0.0
    else:
        coverage = len(matched_chapters) / len(cps) if cps else 0.0

    # --- 4. 置信度与 flag ---
    confidence = _calc_confidence(aligned, hallucinated, coverage)
    flag = _decide_flag(scene, hallucinated, coverage, aligned)

    if coverage < _COVERAGE_THRESHOLDS.get(scene, 0.0) and aligned:
        notes_parts.append(f"覆盖度 {coverage:.0%} 低于 {scene} 场景阈值")
    if not aligned and not hallucinated:
        notes_parts.append("未识别到大纲考核点关键词(可能表述差异较大)")

    return VerifyReport(
        aligned_kps=aligned,
        hallucinated_kps=hallucinated,
        coverage=coverage,
        confidence=confidence,
        flag=flag,
        notes=";".join(notes_parts) if notes_parts else "考核点对齐校验通过",
        matched_chapters=sorted(matched_chapters),
    )


def _detect_soft_hallucinations(text: str, cps: list) -> list[str]:
    """检测软幻觉:输出里的英文/字母数字术语,不在大纲关键词中。

    只对英文/字母数字术语生效——中文同义表述风险高(易把「掌握较好」误判),
    中文幻觉由硬幻觉黑词(:data:`_HARD_HALLUCIN_TERMS`)兜底。

    判定:术语(长度≥3,排除常见缩写 IP/TCP/UDP/HTTP/FTP/DNS/ARP/ICMP/CSMA/VLAN/PPP/URL/WWW/SMTP/POP3/OSI 等)
    不在大纲关键词集 → 疑似超纲。
    """
    # 收集全部大纲关键词(小写)
    all_terms: set[str] = set()
    for cp in cps:
        for t in cp.kp_terms + [cp.chapter]:
            all_terms.add(t.lower())

    # 抽取英文/字母数字术语(长度≥3)
    candidates: list[str] = []
    seen: set[str] = set()
    for m in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", text):
        low = m.lower()
        if low in seen:
            continue
        seen.add(low)
        # 在大纲关键词里出现过 → 跳过
        if any(low in t or t in low for t in all_terms):
            continue
        candidates.append(m)
    return candidates


def _expected_chapters(
    scene: str, context: dict[str, Any], cps: list, text: str
) -> set[str]:
    """该场景应覆盖的章节 code 集合。"""
    if scene == "diagnosis":
        # 诊断场景:weak_points 里给出的知识点对应章节,无则全部章节
        weak = context.get("weak_points") or []
        if weak:
            return _chapters_for_kps(weak, cps)
        return {cp.code for cp in cps}
    if scene == "judge":
        # 判题场景:题干对应章节(单题只考 1-2 个点,期望覆盖=题干命中章节)
        stem = context.get("question_stem") or ""
        return _chapters_for_text(stem, cps)
    # report 场景:全部章节
    return {cp.code for cp in cps}


def _chapters_for_kps(kps: list[str], cps: list) -> set[str]:
    """知识点名称 → 对应章节 code 集合(按关键词命中)。"""
    out: set[str] = set()
    for kp in kps:
        for cp in cps:
            if kp in cp.kp_terms or any(kp in t or t in kp for t in cp.kp_terms):
                out.add(cp.code)
    return out


def _chapters_for_text(text: str, cps: list) -> set[str]:
    """文本 → 对应章节 code 集合(关键词命中)。"""
    out: set[str] = set()
    for cp in cps:
        if any(t and t in text for t in cp.kp_terms):
            out.add(cp.code)
    return out


def _calc_confidence(aligned: list[str], hallucinated: list[str], coverage: float) -> float:
    """置信度:aligned 多 + hallucinated 少 + coverage 高 → 高置信。

    公式:aligned / (aligned + 2*hallucinated + 1) * 0.7 + coverage * 0.3
    幻觉权重加倍惩罚(2x),确保有幻觉时置信度显著下降。
    """
    a = len(aligned)
    h = len(hallucinated)
    base = a / (a + 2 * h + 1)
    conf = base * 0.7 + coverage * 0.3
    # 有硬幻觉直接压到 0.3 以下
    if h > 0:
        conf = min(conf, 0.3)
    return max(0.0, min(1.0, conf))


def _decide_flag(scene: str, hallucinated: list[str], coverage: float, aligned: list[str]) -> str:
    """决定 flag:有硬幻觉 → warn;覆盖过低且有对齐 → warn;否则 pass。"""
    if hallucinated:
        return "warn"
    thresh = _COVERAGE_THRESHOLDS.get(scene, 0.0)
    if thresh > 0 and coverage < thresh and aligned:
        return "warn"
    return "pass"


# ===== 无大纲降级 =====

def _verify_no_syllabus(llm_output: str, scene: str) -> VerifyReport:
    """无大纲时的降级:只做 TF-IDF 自相似度评估,不判对齐/幻觉。"""
    return VerifyReport(
        flag="skipped",
        notes="未加载教学大纲,跳过考核点对齐验证(仅记录输出)",
        confidence=0.0,
    )
