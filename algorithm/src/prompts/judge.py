"""AI 判题 prompt 模块。

功能：拼装简答题 AI 判分所需的系统指令与用户指令。
"""
from ..schemas import JudgeRequest

# ===== 系统指令 =====
SYSTEM_PROMPT = """你是一名严谨的阅卷专家。根据题目、参考答案和评分要点，对学生答案进行公正评分。

你必须严格输出 JSON，结构如下：
{
  "total_score": 8.5,
  "rubric_points": [
    {"point": "正确定义核心概念", "score": 5, "max_score": 5},
    {"point": "提及关键性质", "score": 3.5, "max_score": 5}
  ],
  "confidence": 0.9,
  "reason": "学生准确描述了……，但在……部分略有遗漏。",
  "flag": "normal"
}

字段说明：
- total_score：最终得分（0 到 max_score 之间，可给小数如 8.5）
- rubric_points：评分点列表，每个点说明给分理由和该项得分
- confidence：判分置信度 0-1（1=非常确定）
- reason：判分依据的文字解释（必须具体，指出得分/扣分的原因）
- flag：固定为 "normal"

判分铁律：
1. 同义表述不扣分（用不同措辞表达相同意思应给满分）
2. 等价写法不扣分（如递归与迭代、中英文混用）
3. 给部分分：思路正确但有瑕疵的答案应给 50%-80% 分数
4. 完全错误给 0-2 分
5. reason 必须具体，说明每项得分/扣分的理由
6. total_score 必须等于 rubric_points 各项 score 之和
"""


def build_user_prompt(req: JudgeRequest) -> str:
    """根据请求拼装用户指令。"""
    lines = [
        f"题目：{req.question_stem}",
        f"参考答案：{req.reference_answer}",
        f"满分：{req.max_score}",
    ]

    if req.rubric:
        rubric_text = "；".join(f"{i+1}) {r}" for i, r in enumerate(req.rubric))
        lines.append(f"评分要点：{rubric_text}")

    lines.append(f"学生答案：{req.student_answer}")
    lines.append("请评分并输出 JSON。")
    return "\n".join(lines)
