import logging
from collections.abc import Generator
from datetime import datetime

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程下使用
connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create tables and apply lightweight SQLite-compatible migrations."""
    from app import models  # noqa: F401 触发模型注册
    SQLModel.metadata.create_all(engine)
    _migrate_answer_task()
    _migrate_ai_question()
    _migrate_legacy_tables()
    _migrate_academic_parts()
    _migrate_attitude_homework()
    _migrate_student_answers()


def _migrate_academic_parts() -> None:
    """学业水平六部分默认配置（幂等）。

    - 旧「期末/平时/期中」指标配置迁移为：小班讨论/期中考试/期末考试/考勤/作业/其他
    - 旧维度名「学业成绩」统一更名为「学业水平」
    - 已有五部分配置（缺「作业」）的课程补建作业指标，权重从「其他」让出
    - 没有任何学业水平维度的课程自动补建默认维度与六部分指标
    """
    import json

    from sqlmodel import select

    from app.models import Course, EvalDimension, EvalIndex

    ACADEMIC_NAMES = ("学业成绩", "学业水平")
    DEFAULT_PARTS = [
        ("小班讨论", 10, "discussion"),
        ("期中考试", 30, "midterm"),
        ("期末考试", 30, "final"),
        ("考勤", 10, "attendance"),
        ("作业", 10, "homework"),
        ("其他", 10, "other"),
    ]
    HOMEWORK_WEIGHT = 10.0

    def _rule(idx: EvalIndex) -> dict:
        try:
            return json.loads(idx.score_rule or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def _parts_of(indexes: list[EvalIndex]) -> set[str]:
        return {
            str(_rule(idx).get("part"))
            for idx in indexes
            if _rule(idx).get("type") == "academic_part"
        }

    with Session(engine) as session:
        dims = session.exec(select(EvalDimension)).all()
        academic_dims = [
            d for d in dims if (d.dimension_name or "").strip() in ACADEMIC_NAMES
        ]
        configured_course_ids = {d.course_id for d in academic_dims}

        for dim in academic_dims:
            indexes = list(session.exec(
                select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
            ).all())
            parts = _parts_of(indexes)
            # 已是六部分配置（存在「其他」自动补足与「作业」指标）→ 跳过
            if "other" in parts and "homework" in parts:
                continue
            # 已是五部分配置（有「其他」缺「作业」）→ 补建作业指标，
            # 作业权重从「其他」自动补足指标中让出，保持合计 100%
            if "other" in parts:
                other_idx = next(
                    idx for idx in indexes
                    if _rule(idx).get("type") == "academic_part"
                    and _rule(idx).get("part") == "other"
                )
                homework_weight = min(HOMEWORK_WEIGHT, max(0.0, float(other_idx.weight or 0)))
                session.add(EvalIndex(
                    dimension_id=dim.dimension_id,
                    index_name="作业",
                    weight=homework_weight,
                    score_rule=json.dumps({"type": "academic_part", "part": "homework"}, ensure_ascii=False),
                ))
                other_idx.weight = round(float(other_idx.weight or 0) - homework_weight, 1)
                other_idx.update_time = datetime.now()
                session.add(other_idx)
                session.commit()
                continue
            # 删除旧指标，写入六部分默认
            for idx in indexes:
                session.delete(idx)
            for name, weight, part in DEFAULT_PARTS:
                session.add(EvalIndex(
                    dimension_id=dim.dimension_id,
                    index_name=name,
                    weight=weight,
                    score_rule=json.dumps({"type": "academic_part", "part": part}, ensure_ascii=False),
                ))
            if (dim.dimension_name or "").strip() == "学业成绩":
                dim.dimension_name = "学业水平"
                session.add(dim)
            session.commit()

        # 没有学业水平维度的课程：自动补建默认维度与六部分
        for course_id in session.exec(select(Course.course_id)).all():
            if course_id in configured_course_ids:
                continue
            dim = EvalDimension(
                course_id=course_id,
                dimension_name="学业水平",
                description="课程考核构成配比（小班讨论/期中/期末/考勤/作业/其他，合计固定 100%）",
                sort_num=1,
            )
            session.add(dim)
            session.commit()
            session.refresh(dim)
            for name, weight, part in DEFAULT_PARTS:
                session.add(EvalIndex(
                    dimension_id=dim.dimension_id,
                    index_name=name,
                    weight=weight,
                    score_rule=json.dumps({"type": "academic_part", "part": part}, ensure_ascii=False),
                ))
            session.commit()


def _migrate_attitude_homework() -> None:
    """学习态度维度补建「作业提交」指标（幂等）。

    - 已含作业指标（rule type=homework 或名称含"作业"）的维度跳过
    - 旧默认配置（出勤率/课堂参与 各 50%）升级为新默认 40/30/30
    - 教师自定义配置：作业提交固定 30%，其余指标按比例缩放补足 70%
    - 迁移后重算受影响课程的画像与评价（失败不阻塞启动）
    """
    import json

    from sqlmodel import select

    from app.models import EvalDimension, EvalIndex

    HOMEWORK_WEIGHT = 30.0
    LEGACY_DEFAULT_WEIGHT = 50.0

    def _rule_type(idx: EvalIndex) -> str:
        try:
            return str(json.loads(idx.score_rule or "{}").get("type", ""))
        except (json.JSONDecodeError, TypeError):
            return ""

    with Session(engine) as session:
        dims = session.exec(
            select(EvalDimension).where(EvalDimension.dimension_name.contains("态度"))
        ).all()
        affected_courses: set[int] = set()
        for dim in dims:
            if dim.dimension_id is None:
                continue
            indexes = list(session.exec(
                select(EvalIndex).where(EvalIndex.dimension_id == dim.dimension_id)
            ).all())
            if not indexes:
                continue
            if any(
                _rule_type(idx) == "homework" or "作业" in (idx.index_name or "")
                for idx in indexes
            ):
                continue

            # 旧默认 50/50 → 直接升级为新默认 40/30/30；自定义配置按比例缩放留出 30%
            if (
                len(indexes) == 2
                and all(float(idx.weight or 0) == LEGACY_DEFAULT_WEIGHT for idx in indexes)
            ):
                for idx in indexes:
                    idx.weight = 40.0 if _rule_type(idx) == "attendance" else 30.0
            else:
                rest_sum = sum(float(idx.weight or 0) for idx in indexes)
                scale = (100.0 - HOMEWORK_WEIGHT) / rest_sum if rest_sum > 0 else 1.0
                for idx in indexes:
                    idx.weight = round(float(idx.weight or 0) * scale, 1)
                # 修正在首位指标上吸收舍入误差，保证合计恰为 100
                scaled_sum = round(sum(float(idx.weight) for idx in indexes), 1)
                indexes[0].weight = round(
                    indexes[0].weight + (100.0 - HOMEWORK_WEIGHT - scaled_sum), 1
                )
            for idx in indexes:
                idx.update_time = datetime.now()
                session.add(idx)

            session.add(EvalIndex(
                dimension_id=dim.dimension_id,
                index_name="作业提交",
                weight=HOMEWORK_WEIGHT,
                score_rule=json.dumps({"type": "homework", "full_score": 100}, ensure_ascii=False),
            ))
            if (dim.description or "") == "考勤和课堂参与度":
                dim.description = "考勤、课堂参与度与作业提交率"
                session.add(dim)
            affected_courses.add(dim.course_id)

        if not affected_courses:
            return
        session.commit()

        # 权重变化影响画像（D03 态度分）与综合评价，重算受影响课程
        try:
            from app.services.analysis_refresh import refresh_course_evaluations

            for course_id in sorted(affected_courses):
                refresh_course_evaluations(session, course_id)
        except Exception:
            logging.getLogger(__name__).exception(
                "Attitude homework migration refresh failed (courses=%s)",
                sorted(affected_courses),
            )


def _migrate_student_answers() -> None:
    """答题记录历史数据修复（幂等，每次启动自动执行）。

    - 早期版本反复执行 seed --inject-analysis 会为同一
      (task, student, question) 积累多份重复答题记录，界面得分按记录
      求和会被放大 → 每人每题仅保留最新（answer_id 最大）的一条。
    - 旧种子数据每题按 5 分制存储（5/2/0），与界面 100 分制满分不一致
      → 对"每行分数只可能是 0/2/5 且存在满分 5"的任务，
        按 100/题数 换算为 100 分制。
    """
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "student_answer_record" not in inspector.get_table_names():
            return

        # 1) 去重：同一 (task, student, question) 只保留最新一条
        connection.execute(text(
            """
            DELETE FROM student_answer_record
            WHERE answer_id NOT IN (
                SELECT MAX(answer_id)
                FROM student_answer_record
                GROUP BY task_id, student_id, question_id
            )
            """
        ))

        # 2) 旧 5 分制任务换算为 100 分制
        task_rows = connection.execute(text(
            """
            SELECT sar.task_id,
                   (SELECT COUNT(*) FROM task_question tq
                    WHERE tq.task_id = sar.task_id) AS q_count
            FROM student_answer_record sar
            GROUP BY sar.task_id
            """
        )).all()
        for task_id, q_count in task_rows:
            if not q_count:
                continue
            distinct_scores = {
                row[0] for row in connection.execute(text(
                    "SELECT DISTINCT score FROM student_answer_record WHERE task_id = :tid"
                ), {"tid": task_id}).all()
            }
            # 5 分制特征：所有分数只可能是 0/2/5，且至少存在一个满分 5
            if not distinct_scores or distinct_scores - {0.0, 2.0, 5.0}:
                continue
            factor = (100.0 / q_count) / 5.0
            if factor == 1.0:
                continue
            connection.execute(text(
                "UPDATE student_answer_record SET score = score * :factor WHERE task_id = :tid"
            ), {"factor": factor, "tid": task_id})


def _migrate_ai_question() -> None:
    """Add columns introduced after older ai_question tables were created."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "ai_question" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("ai_question")}
        if "source" not in columns:
            connection.execute(text(
                "ALTER TABLE ai_question ADD COLUMN source "
                "VARCHAR(10) NOT NULL DEFAULT 'manual'"
            ))


def _migrate_answer_task() -> None:
    """Add fields needed by assignments and self-practice to legacy answer_task tables."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "answer_task" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("answer_task")}
        if "task_type" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN task_type "
                "VARCHAR(20) NOT NULL DEFAULT 'assignment'"
            ))
        if "max_attempts" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN max_attempts "
                "INTEGER NOT NULL DEFAULT 1"
            ))
        if "allow_review" not in columns:
            connection.execute(text(
                "ALTER TABLE answer_task ADD COLUMN allow_review "
                "INTEGER NOT NULL DEFAULT 0"
            ))
        connection.execute(
            text(
                "UPDATE answer_task SET task_type = 'self_practice' "
                "WHERE task_name LIKE :prefix"
            ),
            {"prefix": "【自主练习】%"},
        )


def _migrate_answer_task_type() -> None:
    """Backward-compatible alias for older tests/imports."""
    _migrate_answer_task()


def _migrate_legacy_tables() -> None:
    """Backfill columns added while legacy SQLite databases evolved."""
    migrations = {
        "attendance_record": {
            "source_data": "ALTER TABLE attendance_record ADD COLUMN source_data TEXT",
        },
        "class_info": {
            "major": "ALTER TABLE class_info ADD COLUMN major VARCHAR(64) NOT NULL DEFAULT ''",
            "grade": "ALTER TABLE class_info ADD COLUMN grade VARCHAR(16) NOT NULL DEFAULT ''",
        },
        "exam_batch": {
            "semester": "ALTER TABLE exam_batch ADD COLUMN semester VARCHAR(32) NOT NULL DEFAULT ''",
        },
        "score_record": {
            "source_data": "ALTER TABLE score_record ADD COLUMN source_data TEXT",
        },
        "sys_user": {
            "college": "ALTER TABLE sys_user ADD COLUMN college VARCHAR(64)",
        },
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        for table_name, columns in migrations.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, statement in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
        if "class_info" in table_names:
            _backfill_class_dimensions(connection)


def _backfill_class_dimensions(connection) -> None:
    """Recover major and grade from legacy class names when possible."""
    connection.execute(text(
        """
        UPDATE class_info
        SET major = CASE
            WHEN class_name LIKE '计科%' THEN '计算机科学与技术'
            WHEN class_name LIKE '软工%' OR class_name LIKE '软件%' THEN '软件工程'
            WHEN class_name LIKE '数统%' THEN '数学与应用数学'
            ELSE major
        END
        WHERE major IS NULL OR major = ''
        """
    ))
    connection.execute(text(
        """
        UPDATE class_info
        SET grade = '20' || substr(class_name, -5, 2) || '级'
        WHERE (grade IS NULL OR grade = '')
          AND class_name GLOB '*[0-9][0-9][0-9][0-9]班'
        """
    ))


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a database session."""
    with Session(engine) as session:
        yield session