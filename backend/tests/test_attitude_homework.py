"""学习态度维度补建「作业提交」指标迁移测试。

覆盖:
- 旧默认配置（出勤率/课堂参与 各 50%）升级为新默认 40/30/30
- 教师自定义配置按比例缩放（作业提交固定 30%），合计保持 100%
- 已含作业指标的维度跳过；重复执行幂等
- 迁移后画像态度分推导出 0.4/0.3/0.3 的子权重
"""
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.models import Course, EvalDimension, EvalIndex
from app.services.profile import _attitude_component_weights

ATTENDANCE_RULE = '{"type":"attendance","full_score":100}'
INTERACTION_RULE = '{"type":"interaction","full_score":100}'
HOMEWORK_RULE = '{"type":"homework","full_score":100}'


def _make_engine(tmp_path, name: str):
    eng = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Course(course_id=1, course_code="CS101", course_name="计算机网络",
                     teacher_id=1, semester="2025-2026-1", college="计算机学院"))
        s.commit()
    return eng


def _add_attitude_dim(eng, indexes: list[tuple[str, float, str]]) -> int:
    """创建学习态度维度并写入指标，返回 dimension_id。"""
    with Session(eng) as s:
        dim = EvalDimension(course_id=1, dimension_name="学习态度",
                            description="考勤和课堂参与度", sort_num=2)
        s.add(dim)
        s.commit()
        s.refresh(dim)
        for name, weight, rule in indexes:
            s.add(EvalIndex(dimension_id=dim.dimension_id, index_name=name,
                            weight=weight, score_rule=rule))
        s.commit()
        return dim.dimension_id  # type: ignore[return-value]


def _run_migration(monkeypatch, eng) -> None:
    import app.core.database as db_module
    monkeypatch.setattr(db_module, "engine", eng)
    db_module._migrate_attitude_homework()


def _get_indexes(eng, dim_id: int) -> dict[str, EvalIndex]:
    with Session(eng) as s:
        rows = s.exec(select(EvalIndex).where(EvalIndex.dimension_id == dim_id)).all()
        return {i.index_name: i for i in rows}


def test_migrate_legacy_default_upgrades_to_40_30_30(monkeypatch, tmp_path):
    """旧默认 50/50 配置升级为新默认 40/30/30，并推导出正确子权重。"""
    eng = _make_engine(tmp_path, "legacy.db")
    dim_id = _add_attitude_dim(eng, [
        ("出勤率", 50.0, ATTENDANCE_RULE),
        ("课堂参与", 50.0, INTERACTION_RULE),
    ])

    _run_migration(monkeypatch, eng)

    indexes = _get_indexes(eng, dim_id)
    assert set(indexes) == {"出勤率", "课堂参与", "作业提交"}
    assert indexes["出勤率"].weight == 40.0
    assert indexes["课堂参与"].weight == 30.0
    assert indexes["作业提交"].weight == 30.0
    assert sum(i.weight for i in indexes.values()) == 100.0

    # 画像态度分子权重按配置推导：0.4/0.3/0.3
    with Session(eng) as s:
        weights = _attitude_component_weights(s, 1, 0.5, 0.5, 0.0)
    assert weights == (0.4, 0.3, 0.3)


def test_migrate_custom_config_rescales_proportionally(monkeypatch, tmp_path):
    """自定义配置（60/40）：作业提交固定 30%，其余按比例缩放为 42/28。"""
    eng = _make_engine(tmp_path, "custom.db")
    dim_id = _add_attitude_dim(eng, [
        ("出勤率", 60.0, ATTENDANCE_RULE),
        ("课堂参与", 40.0, INTERACTION_RULE),
    ])

    _run_migration(monkeypatch, eng)

    indexes = _get_indexes(eng, dim_id)
    assert indexes["出勤率"].weight == 42.0
    assert indexes["课堂参与"].weight == 28.0
    assert indexes["作业提交"].weight == 30.0
    assert sum(i.weight for i in indexes.values()) == 100.0


def test_migrate_skips_config_with_homework(monkeypatch, tmp_path):
    """已含作业指标的维度不动。"""
    eng = _make_engine(tmp_path, "skip.db")
    dim_id = _add_attitude_dim(eng, [
        ("出勤率", 40.0, ATTENDANCE_RULE),
        ("课堂参与", 30.0, INTERACTION_RULE),
        ("作业提交", 30.0, HOMEWORK_RULE),
    ])

    _run_migration(monkeypatch, eng)

    indexes = _get_indexes(eng, dim_id)
    assert len(indexes) == 3
    assert indexes["出勤率"].weight == 40.0
    assert indexes["课堂参与"].weight == 30.0


def test_migrate_is_idempotent(monkeypatch, tmp_path):
    """重复执行不产生重复指标，权重不再变化。"""
    eng = _make_engine(tmp_path, "idempotent.db")
    dim_id = _add_attitude_dim(eng, [
        ("出勤率", 50.0, ATTENDANCE_RULE),
        ("课堂参与", 50.0, INTERACTION_RULE),
    ])

    _run_migration(monkeypatch, eng)
    _run_migration(monkeypatch, eng)

    indexes = _get_indexes(eng, dim_id)
    assert len(indexes) == 3
    assert sum(i.weight for i in indexes.values()) == 100.0
