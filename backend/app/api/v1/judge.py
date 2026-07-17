"""AI 判题 API。

接口：
    POST /api/v1/judge/short-answer   简答题 AI 判分
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.permissions import require_teaching_user
from app.models import AiQuestion, StudentAnswerRecord

router = APIRouter(dependencies=[Depends(require_teaching_user)])


class ShortAnswerJudgeRequest(BaseModel):
    """简答题判分请求。"""

    question_id: int
    student_answer: str
    student_id: int
    task_id: int = 0


class ShortAnswerJudgeResponse(BaseModel):
    """简答题判分响应。"""

    total_score: float | None
    confidence: float | None = None
    reason: str = ""
    flag: str = "normal"  # normal / manual_required
    rubric_points: list[dict] = []


@router.post("/judge/short-answer", tags=["AI 判题"])
def judge_short_answer(
    req: ShortAnswerJudgeRequest,
    session: Session = Depends(get_session),
) -> dict:
    """简答题 AI 判分。

    流程：查题目（题干+标准答案）→ 调 8001 判分 → 存 StudentAnswerRecord → 返回结果。
    对齐 MVP 验收测试集 TC-B2。
    """
    # 查题目
    question = session.get(AiQuestion, req.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.type != 5:
        raise HTTPException(status_code=400, detail="该题目不是简答题（type=5）")

    # 构造算法服务请求
    payload = {
        "question_stem": question.content,
        "reference_answer": question.correct_answer,
        "rubric": _parse_rubric(question.analysis),
        "student_answer": req.student_answer,
        "max_score": 10.0,
    }

    # 调算法服务
    try:
        resp = httpx.post(
            "http://127.0.0.1:8001/judge_answer",
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        data: dict = resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI 算法服务未启动（8001 端口）")
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:200] if e.response.text else "AI 服务错误"
        raise HTTPException(status_code=503, detail=f"AI 服务错误: {detail}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"算法服务不可达: {e}")

    total_score = data.get("total_score")
    flag = data.get("flag", "normal")
    reason = data.get("reason", "")
    confidence = data.get("confidence")
    rubric_points = data.get("rubric_points", [])

    # 存判分结果到 StudentAnswerRecord
    if total_score is not None:
        # 正常判分：ai_score 和 score 都存（老师可后续覆盖 score）
        is_correct = 1 if total_score >= 6.0 else 0  # ≥60% 算正确
        record = StudentAnswerRecord(
            task_id=req.task_id,
            question_id=req.question_id,
            student_id=req.student_id,
            user_answer=req.student_answer,
            score=float(total_score),
            is_correct=is_correct,
            ai_score=float(total_score),
            judge_reason=reason,
        )
    else:
        # 需人工判分
        record = StudentAnswerRecord(
            task_id=req.task_id,
            question_id=req.question_id,
            student_id=req.student_id,
            user_answer=req.student_answer,
            score=0,
            is_correct=0,
            ai_score=None,
            judge_reason=reason,
        )
    session.add(record)
    session.commit()
    session.refresh(record)

    return {
        "record_id": record.answer_id,
        "total_score": total_score,
        "confidence": confidence,
        "reason": reason,
        "flag": flag,
        "rubric_points": rubric_points,
    }


def _parse_rubric(analysis: str | None) -> list[str] | None:
    """从题目 analysis 字段解析评分要点。

    约定 analysis 中包含"评分要点：1) ... 2) ..."格式的文本。
    简单提取，失败时返回 None。
    """
    if not analysis:
        return None
    # 尝试提取"评分要点"后的内容
    if "评分要点" in analysis:
        parts = analysis.split("评分要点", 1)
        if len(parts) == 2:
            rubric_text = parts[1].lstrip("：:").strip()
            # 按 1) 2) 3) 或数字序号分割
            import re
            items = re.split(r"\d+[)）]", rubric_text)
            items = [item.strip() for item in items if item.strip()]
            if items:
                return items
    return None
