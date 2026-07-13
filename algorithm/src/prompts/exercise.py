"""出题 prompt 模块。

功能：拼装出题所需的系统指令与用户指令。
设计：三段式 = 系统指令（人设+JSON Schema+铁律）+ Few-shot 示例 + 用户需求。
"""
import json
from pathlib import Path

from ..schemas import GenerateRequest

# ===== Few-shot 示例加载 =====
_FEWSHOT_DIR = Path(__file__).parent / "fewshot"


def _load_fewshot(course_name: str) -> list[dict]:
    """加载 few-shot 示例。

    优先按课程名匹配 ``fewshot/{course_key}.json``，找不到则回退到通用数据结构示例。
    所有 few-shot 文件格式：``[{"type":..., "stem":..., "options":..., "answer":..., "explanation":...}]``。
    """
    # 课程名 → 文件 key 的简单映射（取拼音首段或英文）
    key_map = {
        "数据结构": "data_structure",
        "数据结构与算法": "data_structure",
        "计算机网络": "computer_network",
    }
    key = key_map.get(course_name, "data_structure")
    path = _FEWSHOT_DIR / f"{key}.json"
    if not path.exists():
        path = _FEWSHOT_DIR / "data_structure.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===== 系统指令 =====
SYSTEM_PROMPT = """你是一名计算机学院的命题专家。根据给定的知识点和题型，生成符合教学大纲的练习题。

你必须严格输出 JSON，结构如下：
{
  "questions": [
    {
      "type": "single_choice",
      "knowledge_point": "二叉树遍历",
      "difficulty": "medium",
      "stem": "题干文本",
      "options": [{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}, {"key": "C", "text": "选项C"}, {"key": "D", "text": "选项D"}],
      "answer": "A",
      "explanation": "解析说明"
    }
  ]
}

各题型字段要求：
- single_choice（单选）：options 4 个，answer 为单个字母如 "A"
- multi_choice（多选）：options 4 个，answer 为字母升序拼接如 "ABD"
- judge（判断）：options 为 null，answer 为 "true" 或 "false"
- fill_blank（填空）：options 为 null，answer_list 为等价答案列表如 ["链表", "linked list"]，answer 取第一个
- short_answer（简答）：options 为 null，answer 为参考答案（完整文字），explanation 为评分要点

铁律：
1. 题干准确无歧义，选项必须包含 1 个正确答案和 3 个有迷惑性的错误选项。
2. 干扰项要 plausible，不能有明显荒谬选项。
3. 解析简明扼要，说明正确答案的依据。
4. 不同题目之间不得重复（题干、选项、考点均不得雷同）。
5. 所有题目必须严格匹配用户指定的难度（easy/medium/hard），不得自行调整难度分布。
6. 严格按用户指定的知识点出题，不得超出范围。
7. 不得编造不存在的术语或概念。
"""


def build_user_prompt(req: GenerateRequest) -> str:
    """根据请求拼装用户指令。

    包含：课程、知识点、题型分布、难度、（可选）班级掌握度参考、附加要求。
    """
    qt = req.question_types
    lines = [
        f"课程：{req.course_name}",
        f"知识点：{'、'.join(req.knowledge_points)}",
        f"题型分布：单选 {qt.single_choice} 道 / 多选 {qt.multi_choice} 道 / 判断 {qt.judge} 道 / 填空 {qt.fill_blank} 道 / 简答 {qt.short_answer} 道",
        f"难度：{req.difficulty}",
    ]

    # 班级掌握度参考（可选，用于校准难度——让薄弱点的题适当降低难度）
    if req.weak_points:
        wp_text = "；".join(
            f"{w.get('name')}（正确率 {w.get('correct_rate')}）" for w in req.weak_points
        )
        lines.append(f"班级掌握度参考：{wp_text}")

    if req.extra_requirements:
        lines.append(f"其它要求：{req.extra_requirements}")

    lines.append(f"请输出 {req.total_count} 道题的 JSON。")
    return "\n".join(lines)


def build_fewshot_text(course_name: str, max_examples: int = 2) -> str:
    """把 few-shot 示例转成 prompt 文本段落。

    取前 ``max_examples`` 道作为风格示范，告诉 LLM "参照此风格命题"。
    """
    samples = _load_fewshot(course_name)[:max_examples]
    if not samples:
        return ""
    # 紧凑展示：题干 + 答案（不展示完整 options 以节省 token）
    blocks = []
    for i, s in enumerate(samples, 1):
        block = (
            f"示例{i} [{s.get('type','single_choice')}]\n"
            f"题干：{s.get('stem','')}\n"
            f"答案：{s.get('answer','')}\n"
            f"解析：{s.get('explanation','')}"
        )
        blocks.append(block)
    return "以下是命题风格示例（仅供参考风格与严谨度，不要照抄）：\n\n" + "\n\n".join(blocks)


def build_reference_text(reference_questions: list[dict], max_examples: int = 3) -> str:
    """把题库 RAG 检索到的参考题转成 prompt 文本段落。

    与静态 few-shot 相比，reference_questions 来自真实题库，
    包含完整结构（题干+选项+答案+解析），信息更丰富。

    参数：
        reference_questions: 后端检索到的题库原题列表
        max_examples: 最多展示几道（控制 token）
    """
    if not reference_questions:
        return ""

    samples = reference_questions[:max_examples]
    blocks = []
    for i, q in enumerate(samples, 1):
        lines = [
            f"参考题{i} [{q.get('type', 'unknown')}]",
            f"知识点：{q.get('knowledge_point', '')}",
            f"难度：{q.get('difficulty', '')}",
            f"题干：{q.get('stem', '')}",
        ]
        options = q.get("options", "")
        if options:
            lines.append(f"选项：{options}")
        lines.append(f"答案：{q.get('answer', '')}")
        explanation = q.get("explanation", "")
        if explanation:
            lines.append(f"解析：{explanation}")
        blocks.append("\n".join(lines))

    return (
        "以下是从题库检索到的参考题（参照其命题风格、难度和严谨度，"
        "生成同知识点的新题，不得照抄）：\n\n"
        + "\n\n".join(blocks)
    )
