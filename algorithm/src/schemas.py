"""AI 出题的输入输出数据模型（Pydantic）。

定义：
- 请求体：``GenerateRequest``
- 单题结构：``OptionSchema`` / ``QuestionSchema``
- 响应体：``GenerateResponse`` / ``GenerateMeta``
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ===== 题型枚举 =====
QuestionType = Literal["single_choice", "multi_choice", "judge", "fill_blank"]
Difficulty = Literal["easy", "medium", "hard"]


# ===== 请求 =====
class QuestionTypeDistribution(BaseModel):
    """各题型的数量分布。未出现的题型默认 0。"""

    single_choice: int = Field(default=0, ge=0, le=30, description="单选题数量")
    multi_choice: int = Field(default=0, ge=0, le=30, description="多选题数量")
    judge: int = Field(default=0, ge=0, le=30, description="判断题数量")
    fill_blank: int = Field(default=0, ge=0, le=30, description="填空题数量")


class GenerateRequest(BaseModel):
    """AI 出题请求体（后端 → AI 服务）。"""

    course_id: int = Field(..., description="课程 ID")
    course_name: str = Field(..., description="课程名称（供 prompt 使用）")
    knowledge_points: list[str] = Field(..., min_length=1, description="知识点名称列表")
    question_types: QuestionTypeDistribution = Field(
        ..., description="各题型数量分布"
    )
    difficulty: Difficulty = Field(default="medium", description="整体难度")
    extra_requirements: str = Field(default="", max_length=200, description="附加要求")
    # 可选：班级掌握度参考（用于校准难度，支撑亮点 1）
    weak_points: list[dict] | None = Field(
        default=None,
        description="班级薄弱知识点参考：[{name, correct_rate}]",
    )

    @property
    def total_count(self) -> int:
        """本次请求的总题数。"""
        return sum(
            [
                self.question_types.single_choice,
                self.question_types.multi_choice,
                self.question_types.judge,
                self.question_types.fill_blank,
            ]
        )


# ===== 输出 =====
class OptionSchema(BaseModel):
    """选择题选项。"""

    key: str = Field(..., description="选项标识：A/B/C/D")
    text: str = Field(..., description="选项文本")


class QuestionSchema(BaseModel):
    """单道题目的标准结构（LLM 输出强校验目标）。"""

    type: QuestionType
    knowledge_point: str = Field(..., description="题目所属知识点")
    difficulty: Difficulty = Field(default="medium")
    stem: str = Field(..., min_length=4, description="题干")
    options: list[OptionSchema] | None = Field(
        default=None, description="选项（选择题必填，判断/填空为空）"
    )
    answer: str = Field(..., description="标准答案")
    answer_list: list[str] | None = Field(
        default=None, description="填空题等价答案列表"
    )
    explanation: str = Field(default="", description="解析")


class GenerateMeta(BaseModel):
    """本次生成的元信息（供追溯与展示）。"""

    model: str = Field(..., description="使用的模型名")
    elapsed_ms: int = Field(..., description="总耗时（毫秒）")
    input_tokens: int = Field(default=0, description="输入 token")
    output_tokens: int = Field(default=0, description="输出 token")
    success_count: int = Field(..., description="最终合格题目数")
    filtered_count: int = Field(default=0, description="被过滤掉的题目数")
    retry_count: int = Field(default=0, description="重试次数")


class GenerateResponse(BaseModel):
    """AI 出题响应体（AI 服务 → 后端）。"""

    questions: list[QuestionSchema]
    meta: GenerateMeta


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    detail: str
