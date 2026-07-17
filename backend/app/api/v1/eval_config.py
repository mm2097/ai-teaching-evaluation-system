"""评价指标体系配置 API（Eval.Config）。

任课教师可自定义本人课程的评价维度、指标、权重与评分规则。
- 维度 CRUD（Eval.Config.Dimension）
- 指标 CRUD + 权重校验（Eval.Config.Weight）
- 评分规则配置（Eval.Config.Rule）
- 仅任课教师可操作（Eval.Config.UserValid）
"""

from __future__ import annotations

import json as _json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Query as QueryParam
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.api.v1.analysis import _check_course_access
from app.models import (
    Course,
    EvalDimension,
    EvalDimensionScore,
    EvalIndex,
    StudentEvaluationResult,
    SysUser,
    SysRole,
)

router = APIRouter()


# ============================================================================
# 工具函数
# ============================================================================

def _unwrap(val: Any, default: Any = None) -> Any:
    """绕过 FastAPI Query 包装，取真实参数值。

    FastAPI 的 Query(default=...) 在直接 Python 调用时返回 Query 对象而非默认值。
    """
    if isinstance(val, QueryParam):
        return default
    return val


# ============================================================================
# 权限校验
# ============================================================================

def _require_teacher(current_user: SysUser, session: Session) -> None:
    """仅任课教师可操作评价体系配置（Eval.Config.UserValid）。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""
    if role_code != "teacher":
        raise HTTPException(
            status_code=403,
            detail="仅任课教师可操作评价体系配置",
        )


# ============================================================================
# 权重校验
# ============================================================================

def _validate_dimension_weights(
    session: Session,
    dimension_id: int,
    *,
    exclude_index_id: int | None = None,
    extra_weight: float = 0,
) -> tuple[float, bool]:
    """计算维度下所有指标权重总和并校验是否 = 100。

    exclude_index_id: 编辑模式排除自身的旧权重
    extra_weight: 新增/更新后的权重值
    返回 (total, is_valid)
    """
    stmt = select(EvalIndex).where(EvalIndex.dimension_id == dimension_id)
    indexes = session.exec(stmt).all()

    total = sum(
        i.weight for i in indexes
        if exclude_index_id is None or i.index_id != exclude_index_id
    )
    total += extra_weight
    is_valid = abs(total - 100.0) < 0.01
    return round(total, 1), is_valid


# ============================================================================
# 辅助序列化
# ============================================================================

def _parse_score_rule(raw: str | dict | None) -> dict:
    """将 score_rule 解析为 dict。"""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return _json.loads(raw)
    except (_json.JSONDecodeError, TypeError):
        return {}


def _dimension_to_dict(d: EvalDimension, indexes: list[EvalIndex]) -> dict:
    """序列化维度及其指标，包含权重校验信息。"""
    idx_list = []
    for i in sorted(indexes, key=lambda x: x.index_id or 0):
        idx_list.append({
            "indexId": i.index_id,
            "indexName": i.index_name,
            "weight": i.weight,
            "scoreRule": _parse_score_rule(i.score_rule),
            "description": i.description,
        })
    weight_sum = round(sum(i.weight for i in indexes), 1)
    return {
        "dimensionId": d.dimension_id,
        "dimensionName": d.dimension_name,
        "description": d.description,
        "sortNum": d.sort_num,
        "indexes": idx_list,
        "weightSum": weight_sum,
        "weightValid": abs(weight_sum - 100.0) < 0.01,
    }


# ============================================================================
# 1. 查看课程完整评价体系
# ============================================================================

@router.get("/eval-config/{course_id}", tags=["评价配置"])
def get_eval_config(
    course_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """查看课程的完整评价指标体系（Eval.Config）。

    返回课程下所有维度及其指标、权重、评分规则、权重校验状态。

    权限（Eval.Config.UserValid）：仅任课教师。
    """
    _require_teacher(current_user, session)
    _check_course_access(session, current_user, course_id)

    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    dimensions = session.exec(
        select(EvalDimension)
        .where(EvalDimension.course_id == course_id)
        .order_by(EvalDimension.sort_num)
    ).all()

    dim_list = []
    for d in dimensions:
        indexes = session.exec(
            select(EvalIndex).where(EvalIndex.dimension_id == d.dimension_id)
        ).all()
        dim_list.append(_dimension_to_dict(d, list(indexes)))

    return {
        "courseId": course_id,
        "courseName": course.course_name,
        "dimensions": dim_list,
    }


# ============================================================================
# 2. 维度 CRUD（Eval.Config.Dimension）
# ============================================================================

@router.post("/eval-config/{course_id}/dimensions", tags=["评价配置"])
def create_dimension(
    course_id: int,
    dimension_name: str = Query(..., max_length=32, description="维度名称"),
    description: str | None = Query(default=None, max_length=255),
    sort_num: int = Query(default=0, description="排序号"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """新增评价维度（Eval.Config.Dimension）。"""
    _require_teacher(current_user, session)
    _check_course_access(session, current_user, course_id)

    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    _description = _unwrap(description, None)
    _sort_num = _unwrap(sort_num, 0)

    dim = EvalDimension(
        course_id=course_id,
        dimension_name=dimension_name,
        description=_description,
        sort_num=_sort_num,
    )
    session.add(dim)
    session.commit()
    session.refresh(dim)

    return {
        "dimensionId": dim.dimension_id,
        "dimensionName": dim.dimension_name,
        "description": dim.description,
        "sortNum": dim.sort_num,
        "courseId": course_id,
        "indexes": [],
        "weightSum": 0,
        "weightValid": False,
    }


@router.put("/eval-config/dimensions/{dimension_id}", tags=["评价配置"])
def update_dimension(
    dimension_id: int,
    dimension_name: str | None = Query(default=None, max_length=32),
    description: str | None = Query(default=None, max_length=255),
    sort_num: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """编辑评价维度（Eval.Config.Dimension）。"""
    _require_teacher(current_user, session)

    dim = session.get(EvalDimension, dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="维度不存在")
    _check_course_access(session, current_user, dim.course_id)

    _dimension_name = _unwrap(dimension_name, None)
    _description = _unwrap(description, None)
    _sort_num = _unwrap(sort_num, None)

    if _dimension_name is not None:
        dim.dimension_name = _dimension_name
    if _description is not None:
        dim.description = _description
    if _sort_num is not None:
        dim.sort_num = _sort_num
    dim.update_time = datetime.now()

    session.add(dim)
    session.commit()
    session.refresh(dim)

    indexes = session.exec(
        select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
    ).all()

    return _dimension_to_dict(dim, list(indexes))


@router.delete("/eval-config/dimensions/{dimension_id}", tags=["评价配置"])
def delete_dimension(
    dimension_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """删除评价维度，同时级联删除其下全部指标（Eval.Config.Dimension）。

    会同步清理已存在的评价结果中该维度的得分记录。
    """
    _require_teacher(current_user, session)

    dim = session.get(EvalDimension, dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="维度不存在")
    _check_course_access(session, current_user, dim.course_id)

    course_id = dim.course_id

    # 级联删除指标
    indexes = session.exec(
        select(EvalIndex).where(EvalIndex.dimension_id == dimension_id)
    ).all()
    for idx in indexes:
        session.delete(idx)

    # 清除关联的维度得分
    scores = session.exec(
        select(EvalDimensionScore).where(EvalDimensionScore.dimension_id == dimension_id)
    ).all()
    for s in scores:
        session.delete(s)

    dim_name = dim.dimension_name
    session.delete(dim)
    session.commit()

    return {
        "message": f"维度「{dim_name}」及其 {len(indexes)} 个指标已删除",
        "deletedDimensionId": dimension_id,
        "deletedIndexCount": len(indexes),
        "courseId": course_id,
    }


# ============================================================================
# 3. 指标 CRUD（Eval.Config.Weight + Eval.Config.Rule）
# ============================================================================

@router.post("/eval-config/dimensions/{dimension_id}/indexes", tags=["评价配置"])
def create_index(
    dimension_id: int,
    index_name: str = Query(..., max_length=64, description="指标名称"),
    weight: float = Query(..., ge=0, le=100, description="权重百分比（0-100）"),
    score_rule: str | None = Query(default=None, description="评分规则 JSON 字符串"),
    description: str | None = Query(default=None, max_length=255),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """新增评价指标（Eval.Config.Dimension）。

    自动校验该维度下所有指标的权重总和是否超过 100%（Eval.Config.Weight）。
    """
    _require_teacher(current_user, session)

    dim = session.get(EvalDimension, dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="维度不存在")
    _check_course_access(session, current_user, dim.course_id)

    # Unwrap Query params（直接 Python 调用时的兼容处理）
    _score_rule = _unwrap(score_rule, None)
    _description = _unwrap(description, None)

    # 权重校验
    total, is_valid = _validate_dimension_weights(
        session, dimension_id, extra_weight=weight
    )
    if total > 100:
        raise HTTPException(
            status_code=400,
            detail=f"权重总和为 {total}%，超过 100%。当前维度已有指标权重之和加上新指标权重 ({weight}%) 超出上限，请调整",
        )

    # 校验 score_rule JSON 格式
    rule_str = None
    if _score_rule:
        try:
            parsed = _json.loads(_score_rule) if isinstance(_score_rule, str) else _score_rule
            rule_str = _json.dumps(parsed, ensure_ascii=False)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="score_rule 不是有效的 JSON 格式")

    idx = EvalIndex(
        dimension_id=dimension_id,
        index_name=index_name,
        weight=weight,
        score_rule=rule_str or "",
        description=_description,
    )
    session.add(idx)
    session.commit()
    session.refresh(idx)

    return {
        "indexId": idx.index_id,
        "dimensionId": dimension_id,
        "indexName": idx.index_name,
        "weight": idx.weight,
        "scoreRule": _parse_score_rule(idx.score_rule),
        "description": idx.description,
        "weightSumAfterAdd": total,
        "weightValid": is_valid or abs(total - 100.0) < 0.01,
    }


@router.put("/eval-config/indexes/{index_id}", tags=["评价配置"])
def update_index(
    index_id: int,
    index_name: str | None = Query(default=None, max_length=64),
    weight: float | None = Query(default=None, ge=0, le=100),
    score_rule: str | None = Query(default=None),
    description: str | None = Query(default=None, max_length=255),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """编辑评价指标（Eval.Config.Weight + Eval.Config.Rule）。

    修改权重时自动校验该维度下权重总和是否超过 100%。
    """
    _require_teacher(current_user, session)

    idx = session.get(EvalIndex, index_id)
    if not idx:
        raise HTTPException(status_code=404, detail="指标不存在")
    dim = session.get(EvalDimension, idx.dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="评价维度不存在")
    _check_course_access(session, current_user, dim.course_id)

    # Unwrap Query params
    _weight = _unwrap(weight, None)
    _score_rule = _unwrap(score_rule, None)
    _description = _unwrap(description, None)
    _index_name = _unwrap(index_name, None)

    new_weight = _weight if _weight is not None else idx.weight

    # 权重校验（排除自身旧权重）
    if _weight is not None:
        total, is_valid = _validate_dimension_weights(
            session, idx.dimension_id,
            exclude_index_id=index_id, extra_weight=new_weight,
        )
        if total > 100:
            raise HTTPException(
                status_code=400,
                detail=f"修改后权重总和为 {total}%，超过 100%。当前维度其他指标权重之和为 {round(total - new_weight, 1)}%，加上新权重 {new_weight}% 超出上限，请调整",
            )
    else:
        total, is_valid = _validate_dimension_weights(
            session, idx.dimension_id, extra_weight=0,
        )

    if _index_name is not None:
        idx.index_name = _index_name
    if _weight is not None:
        idx.weight = _weight
    if _score_rule is not None:
        try:
            parsed = _json.loads(_score_rule) if isinstance(_score_rule, str) else _score_rule
            idx.score_rule = _json.dumps(parsed, ensure_ascii=False)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="score_rule 不是有效的 JSON 格式")
    if _description is not None:
        idx.description = _description

    idx.update_time = datetime.now()
    session.add(idx)
    session.commit()
    session.refresh(idx)

    return {
        "indexId": idx.index_id,
        "dimensionId": idx.dimension_id,
        "indexName": idx.index_name,
        "weight": idx.weight,
        "scoreRule": _parse_score_rule(idx.score_rule),
        "description": idx.description,
        "weightSumAfterEdit": total,
        "weightValid": abs(total - 100.0) < 0.01,
    }


@router.delete("/eval-config/indexes/{index_id}", tags=["评价配置"])
def delete_index(
    index_id: int,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """删除评价指标（Eval.Config.Dimension）。

    返回删除后该维度剩余指标的权重总和以供前端校验。
    """
    _require_teacher(current_user, session)

    idx = session.get(EvalIndex, index_id)
    if not idx:
        raise HTTPException(status_code=404, detail="指标不存在")
    dim = session.get(EvalDimension, idx.dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="评价维度不存在")
    _check_course_access(session, current_user, dim.course_id)

    dimension_id = idx.dimension_id
    index_name = idx.index_name

    session.delete(idx)
    session.commit()

    # 返回删除后的权重状态
    total, is_valid = _validate_dimension_weights(
        session, dimension_id, extra_weight=0,
    )

    return {
        "message": f"指标「{index_name}」已删除",
        "deletedIndexId": index_id,
        "dimensionId": dimension_id,
        "weightSumAfterDelete": total,
        "weightValid": is_valid,
    }
