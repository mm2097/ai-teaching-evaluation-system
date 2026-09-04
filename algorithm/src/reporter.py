"""D10 报告结论与建议 - LLM 增强层。

流程（双轨）：
    [统计指标] → 模板兜底（必走，在 backend/app/services/report_template.py）
              → LLM 增强（本模块，可选）

LLM 成功 → 用 LLM 版本覆盖模板；
LLM 失败/超时 → 保留模板版本（backend 层自动回退）。

被调用方式：
    - 后端通过 HTTP POST /generate_report 调用
    - 入参：模板已生成的 ctx + 模板文本
    - 出参：增强后文本 + source 标识（llm / template_fallback）
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from loguru import logger

from .llm_client import get_llm_client


SYSTEM_PROMPT = """你是一名资深的「教学分析报告撰写助手」，服务于高校计算机学院任课教师。

你的任务：基于结构化统计数据与模板初稿，改写成自然、专业、可执行的分析报告。

铁律：
1. **严禁编造**：所有数字、人名、知识点、维度名、指标名必须来自输入数据，不得增减。
2. **听主题**：不同类型报告侧重点不同，禁止写成同一篇。
   - 1 班级学情：人数、历次考核、分档、出勤、预警；知识点只附带一句。
   - 2 学生个人学情：该生轨迹、画像标签、教师配置维度得分。
   - 3 知识点分析：按模块/知识点掌握度；不要展开及格率或预警名单。
   - 4 学习质量：必须用教师自定义的维度名、指标名和权重，引用 eval_snapshot；禁止擅自改成「学业成绩/学习态度」等默认叫法。
3. **写细**：400–700 字。suggestion 用 1. 2. 3. 换行，每条对应具体数据。
4. 输出严格 JSON：{"summary": "...", "conclusion": "...", "suggestion": "..."}
"""


@dataclass
class ReportRequest:
    """报告增强请求。"""

    scope: str                 # class / student
    template: dict             # 模板生成的初稿 {summary, conclusion, suggestion}
    context: dict              # 结构化统计指标（ReportContext 序列化）


def enhance_report(scope: str, template: dict, context: dict) -> dict:
    """对模板报告做 LLM 增强。

    返回：
        成功：{summary, conclusion, suggestion, source:"llm"}
        失败：{summary, conclusion, suggestion, source:"template_fallback", error:...}
    """
    user_prompt = _build_user_prompt(scope, template, context)
    client = get_llm_client()

    try:
        result = client.chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_mode=True,
        )
        parsed = _parse_json(result.content)
        if not parsed or not _validate(parsed):
            logger.warning(f"LLM 报告 JSON 校验失败，回退模板。原始前200字：{result.content[:200]}")
            return _fallback(template, "LLM 输出校验失败")

        return {
            "summary": parsed["summary"],
            "conclusion": parsed["conclusion"],
            "suggestion": parsed["suggestion"],
            "source": "llm",
            "meta": {
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        }
    except RuntimeError as e:
        logger.warning(f"LLM 报告增强失败，回退模板：{e}")
        return _fallback(template, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"报告增强未预期异常：{e}")
        return _fallback(template, str(e))


def _build_user_prompt(scope: str, template: dict, context: dict) -> str:
    """拼装用户指令。"""
    type_name = context.get("report_type_name") or ("班级整体报告" if scope == "class" else "学生个人报告")
    report_type = context.get("report_type")
    focus = {
        1: "只写班级学情（考核、分档、出勤、预警）。",
        2: "只写该生个人学情（轨迹、标签、教师配置维度）。",
        3: "只写知识点/模块掌握度。",
        4: "只写教师自定义评价方案下的学习质量，保留维度与指标原名。",
    }.get(int(report_type) if report_type is not None else 0, "按模板主题改写。")
    return (
        f"请改写以下「{type_name}」初稿。{focus}\n\n"
        f"【模板初稿】\n{json.dumps(template, ensure_ascii=False, indent=2)}\n\n"
        f"【统计数据】\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        f"要求：保留关键数字、教师配置的维度/指标名称与权重；建议分条；输出严格 JSON："
        f"{{\"summary\":\"...\",\"conclusion\":\"...\",\"suggestion\":\"...\"}}"
    )


def _parse_json(content: str) -> dict | None:
    """解析 JSON，兼容 ```json``` 代码块。"""
    import re
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _validate(parsed: dict) -> bool:
    """LLM 输出最低校验：三个字段都非空字符串。"""
    return all(
        isinstance(parsed.get(k), str) and parsed.get(k).strip()
        for k in ("summary", "conclusion", "suggestion")
    )


def _fallback(template: dict, error: str) -> dict:
    return {
        "summary": template.get("summary", ""),
        "conclusion": template.get("conclusion", ""),
        "suggestion": template.get("suggestion", ""),
        "source": "template_fallback",
        "error": error[:200],
    }
