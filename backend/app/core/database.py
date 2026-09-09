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
    # 先加 eval_dimension.weight 列，后续迁移（academic_parts 等）查询该表时才不会报缺列
    _migrate_dimension_weight()
    _migrate_legacy_tables()
    # Academic-part migration reads EvalDimension.weight, so add/backfill that
    # column before querying the evaluation tables on legacy databases.
    _migrate_dimension_weight()
    _migrate_academic_parts()
    _migrate_attitude_homework()
    _rename_homework_index()
    _migrate_evaluation_levels()
    _migrate_student_answers()
    _migrate_split_combined_knowledge_points()
    _migrate_student_answer_verify()


def _migrate_evaluation_levels() -> None:
    """综合得分评价等级统一为五档（幂等）。

    旧等级标准（优≥85 / 良75-85 / 中60-75 / 差<60）与综合看板
    「班级成绩等级分布」、学习质量页「分数段分布」的五档分数等级
    （优秀≥90 / 良好80-89 / 中等70-79 / 合格60-69 / 不合格<60）不一致，
    按已落库总分重算全部评价等级。
    """
    from sqlmodel import select

    from app.models import StudentEvaluationResult
    from app.services.evaluation import score_to_level

    with Session(engine) as session:
        rows = session.exec(select(StudentEvaluationResult)).all()
        changed = 0
        for row in rows:
            new_level = score_to_level(float(row.total_score or 0))
            if row.eval_level != new_level:
                row.eval_level = new_level
                session.add(row)
                changed += 1
        if changed:
            session.commit()


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
                weight=60.0,
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
    """学习态度维度补建「测试提交」指标（幂等，原「作业提交」）。

    - 已含作业指标（rule type=homework 或名称含"作业"/"测试提交"）的维度跳过
    - 旧默认配置（出勤率/课堂参与 各 50%）升级为新默认 40/30/30
    - 教师自定义配置：测试提交固定 30%，其余指标按比例缩放补足 70%
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
                _rule_type(idx) == "homework"
                or "作业" in (idx.index_name or "")
                or "测试提交" in (idx.index_name or "")
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
                index_name="测试提交",
                weight=HOMEWORK_WEIGHT,
                score_rule=json.dumps({"type": "homework", "full_score": 100}, ensure_ascii=False),
            ))
            if (dim.description or "") == "考勤和课堂参与度":
                dim.description = "考勤、课堂参与度与测试提交率"
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


def _rename_homework_index() -> None:
    """存量「作业提交」指标更名为「测试提交」（幂等）。

    该指标基于答题任务提交情况（score_rule type=homework），与教师上传的
    作业单项成绩无关，更名避免歧义：
    - EvalIndex：rule type=homework 且名称为「作业提交/作业提交率」→「测试提交」
    - EvalDimension：描述含「作业提交率」→「测试提交率」
    仅改名称，权重与规则不变，无需重算得分。
    """
    import json

    from sqlmodel import select

    from app.models import EvalDimension, EvalIndex

    with Session(engine) as session:
        renamed = False
        for idx in session.exec(select(EvalIndex)).all():
            try:
                rule = json.loads(idx.score_rule or "{}")
            except (json.JSONDecodeError, TypeError):
                rule = {}
            if rule.get("type") == "homework" and (idx.index_name or "") in ("作业提交", "作业提交率"):
                idx.index_name = "测试提交"
                idx.update_time = datetime.now()
                session.add(idx)
                renamed = True
        for dim in session.exec(select(EvalDimension)).all():
            if "作业提交率" in (dim.description or ""):
                dim.description = (dim.description or "").replace("作业提交率", "测试提交率")
                dim.update_time = datetime.now()
                session.add(dim)
                renamed = True
        if renamed:
            session.commit()


def _migrate_dimension_weight() -> None:
    """eval_dimension 增加 weight 列并回填默认维度占比（幂等）。

    默认维度只有两个：学业水平 60% + 学习态度 40%（合计 100%，直接生效）。
    - 建列当次回填：学业成绩/学业水平→60、学习态度→40，
      其余（学习进步/知识掌握/自定义维度）保持 0，由教师自行分配
    - 已有维度但缺「学习态度」的课程自动补建该维度与三个标准指标
      （出勤率 40 / 课堂参与 30 / 测试提交 30，同 _migrate_academic_parts 补建学业水平的模式）
    - 回填/补建影响综合评价口径与维度分落库 → 重算受影响课程（失败不阻塞启动）
    """
    import json

    from sqlmodel import select

    from app.models import Course, EvalDimension, EvalIndex

    # 1) 建列（幂等；仅建列当次回填，避免重启覆盖教师手改的占比）
    column_added = False
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "eval_dimension" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("eval_dimension")}
        if "weight" not in columns:
            connection.execute(text(
                "ALTER TABLE eval_dimension ADD COLUMN weight FLOAT NOT NULL DEFAULT 0"
            ))
            column_added = True

    DEFAULT_SHARE = {"学业成绩": 60.0, "学业水平": 60.0, "学习态度": 40.0}
    ATTITUDE_INDEXES = [
        ("出勤率", 40.0, {"type": "attendance", "full_score": 100}),
        ("课堂参与", 30.0, {"type": "interaction", "full_score": 100}),
        ("测试提交", 30.0, {"type": "homework", "full_score": 100}),
    ]
    refreshed: set[int] = set()

    with Session(engine) as session:
        dims = session.exec(select(EvalDimension)).all()

        # 2) 建列当次回填 canonical 默认占比
        if column_added:
            for dim in dims:
                share = DEFAULT_SHARE.get((dim.dimension_name or "").strip())
                if share is not None and float(dim.weight or 0) != share:
                    dim.weight = share
                    dim.update_time = datetime.now()
                    session.add(dim)
                    if dim.course_id is not None:
                        refreshed.add(dim.course_id)

        # 修复旧版本后补建学业维度留下的 0/40 配置。仅处理总占比不完整且
        # 恰好符合旧缺陷特征的课程，不覆盖教师已经配置完整的自定义方案。
        dims_by_course: dict[int, list[EvalDimension]] = {}
        for dim in dims:
            dims_by_course.setdefault(dim.course_id, []).append(dim)
        for course_id, course_dims in dims_by_course.items():
            academic_dims = [
                dim for dim in course_dims
                if (dim.dimension_name or "").strip() in ("学业成绩", "学业水平")
            ]
            attitude_share = sum(
                float(dim.weight or 0) for dim in course_dims
                if "态度" in (dim.dimension_name or "")
            )
            total_share = sum(float(dim.weight or 0) for dim in course_dims)
            if (
                len(academic_dims) == 1
                and float(academic_dims[0].weight or 0) == 0
                and abs(attitude_share - 40.0) < 0.01
                and abs(total_share - 40.0) < 0.01
            ):
                academic_dims[0].weight = 60.0
                academic_dims[0].update_time = datetime.now()
                session.add(academic_dims[0])
                refreshed.add(course_id)

        # 3) 补建默认「学习态度」维度（幂等，每次启动检查）
        attitude_course_ids = {
            d.course_id for d in dims if "态度" in (d.dimension_name or "")
        }
        for course_id in session.exec(select(Course.course_id)).all():
            if course_id in attitude_course_ids:
                continue
            dim = EvalDimension(
                course_id=course_id,
                dimension_name="学习态度",
                description="考勤、课堂参与度与测试提交率",
                sort_num=2,
                weight=40.0,
            )
            session.add(dim)
            session.commit()
            session.refresh(dim)
            for name, weight, rule in ATTITUDE_INDEXES:
                session.add(EvalIndex(
                    dimension_id=dim.dimension_id,
                    index_name=name,
                    weight=weight,
                    score_rule=json.dumps(rule, ensure_ascii=False),
                ))
            session.commit()
            refreshed.add(course_id)

        session.commit()

    # 4) 重算受影响课程（占比口径变化 + 新维度得分落库）
    if not refreshed:
        return
    try:
        from app.services.analysis_refresh import refresh_course_evaluations

        for course_id in sorted(refreshed):
            with Session(engine) as bg_session:
                refresh_course_evaluations(bg_session, course_id)
    except Exception:
        logging.getLogger(__name__).exception(
            "Dimension weight migration refresh failed (courses=%s)",
            sorted(refreshed),
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


def _migrate_split_combined_knowledge_points() -> None:
    """历史复合知识点（如「传输时延、TCP/UDP协议」）拆分（幂等）。

    早期导入把一格多个知识点整体建为一个知识点，考试扣分无法归属到
    具体知识点。现将名称含分隔符（、/，/；）的知识点拆分为多个独立
    知识点：
    - 拆分片段在课程内同名知识点已存在时复用，否则在原模块下新建
    - 删除复合点的掌握度记录与复合点自身（CourseTestDetail 中的原始
      文本不动，计算掌握度/失分率时按分隔符拆分归属）
    - AiQuestion 若引用复合点，改挂到第一个拆分片段
    - 重算受影响课程的全部分析（失败不阻塞启动）
    """
    from sqlmodel import select

    from app.models import AiQuestion, KnowledgeMastery, KnowledgeModule, KnowledgePoint
    from app.services.knowledge_utils import split_knowledge_names

    with Session(engine) as session:
        combined_points = [
            p for p in session.exec(select(KnowledgePoint)).all()
            if len(split_knowledge_names(p.point_name)) > 1
        ]
        if not combined_points:
            return

        affected_courses: set[int] = set()
        for point in combined_points:
            module = session.get(KnowledgeModule, point.module_id)
            course_id = module.course_id if module else None
            if course_id is None:
                continue
            affected_courses.add(course_id)

            # 课程内知识点按名称查重（跨模块复用同名点，避免拆出重复点）
            course_module_ids = [
                m.module_id
                for m in session.exec(
                    select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
                ).all()
            ]
            existing_by_name = {
                p2.point_name.strip(): p2
                for p2 in session.exec(
                    select(KnowledgePoint).where(
                        KnowledgePoint.module_id.in_(course_module_ids)  # type: ignore[arg-type]
                    )
                ).all()
                if p2.point_id != point.point_id
            }

            split_points = []
            for piece in split_knowledge_names(point.point_name):
                target = existing_by_name.get(piece)
                if target is None:
                    target = KnowledgePoint(
                        module_id=point.module_id,
                        point_name=piece,
                        description="",
                        sort_num=0,
                    )
                    session.add(target)
                    session.flush()
                    existing_by_name[piece] = target
                split_points.append(target)

            # AiQuestion 引用复合点 → 改挂第一个拆分片段
            for question in session.exec(
                select(AiQuestion).where(AiQuestion.point_id == point.point_id)
            ).all():
                question.point_id = split_points[0].point_id
                session.add(question)

            # 清理复合点的掌握度记录与复合点自身
            for km in session.exec(
                select(KnowledgeMastery).where(KnowledgeMastery.point_id == point.point_id)
            ).all():
                session.delete(km)
            session.delete(point)

        session.commit()

    # 扣分归属口径变化 → 重算受影响课程的掌握度与画像（失败不阻塞启动）
    try:
        from app.services.analysis_refresh import refresh_course_analysis

        for course_id in sorted(affected_courses):
            with Session(engine) as bg_session:
                refresh_course_analysis(bg_session, course_id)
    except Exception:
        logging.getLogger(__name__).exception(
            "Split combined knowledge points refresh failed (courses=%s)",
            sorted(affected_courses),
        )


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
            # SQLite 的 ADD COLUMN 不允许非常量默认值，默认串仅存在于
            # 补列瞬间，随后立即被下方回填覆盖为 create_time
            "exam_time": "ALTER TABLE exam_batch ADD COLUMN exam_time DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'",
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
        added_columns: set[tuple[str, str]] = set()
        exam_batch_had_create_time = False
        for table_name, columns in migrations.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            if table_name == "exam_batch":
                exam_batch_had_create_time = "create_time" in existing_columns
            for column_name, statement in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
                    added_columns.add((table_name, column_name))
        if ("exam_batch", "exam_time") in added_columns:
            # 补列时存量批次回填考核时间以保持考核时间序（仅补列当次执行）：
            # 优先用批次创建时间；极早期 schema 无 create_time 列时退化为迁移时刻
            backfill = (
                "COALESCE(create_time, CURRENT_TIMESTAMP)"
                if exam_batch_had_create_time
                else "CURRENT_TIMESTAMP"
            )
            connection.execute(text(
                f"UPDATE exam_batch SET exam_time = {backfill}"
            ))
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


def _migrate_student_answer_verify() -> None:
    """student_answer_record 补建 verify_report 列(大小模型协同验证报告,幂等)。"""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "student_answer_record" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("student_answer_record")}
        if "verify_report" not in columns:
            connection.execute(text(
                "ALTER TABLE student_answer_record ADD COLUMN verify_report TEXT"
            ))
