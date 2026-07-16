"""分析 API：学情画像、知识点热力图、预警、成绩预测。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    Student, Course, CourseStudent, ClassInfo,
    KnowledgeMastery, KnowledgePoint, KnowledgeModule,
    StudyWarning, StudentProfile,
    ScoreRecord, EvalDimensionScore, StudentEvaluationResult,
    SysUser, Teacher, SysRole,
    IndividualScore, CourseTestDetail, ExamBatch,
)
from app.services.predict import predict_student_scores
from app.services.mastery import compute_assignment_accuracy_index, compute_mastery_index_with_fallback
from app.services.warning import scan_course_warnings, persist_warnings

router = APIRouter()


# ============================================================================
# 权限校验辅助
# ============================================================================

def _check_profile_access(
    current_user: SysUser,
    student_id: int,
    course_id: int | None,
    session: Session,
) -> None:
    """校验学情画像查看权限（Analysis.Profile.UserValid）。

    - 任课教师（teacher）：仅可查看自己授课课程内的学生画像
    - 学生（student）：仅可查看自己的画像
    - 管理员（admin）：不参与教学分析
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    # 校验学生是否存在
    target_student = session.get(Student, student_id)
    if not target_student:
        raise HTTPException(status_code=404, detail=f"学生不存在（student_id={student_id}）")

    # 学生：只能看自己（Analysis.Profile.UserValid.Logined）
    if role_code == "student":
        student = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not student or student.student_id != student_id:
            raise HTTPException(
                status_code=403,
                detail="学生仅可查看自己的学情画像",
            )
        return

    # 任课教师：只能看自己授课课程的学生
    if role_code == "teacher":
        teacher = session.exec(
            select(Teacher).where(Teacher.user_id == current_user.user_id)
        ).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="当前账号未关联教师信息")

        if course_id is not None:
            # 指定课程：校验教师是否是该课程授课教师
            course = session.get(Course, course_id)
            if not course:
                raise HTTPException(status_code=404, detail="课程不存在")
            if course.teacher_id != teacher.teacher_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"仅授课教师可查看课程「{course.course_name}」的学情画像",
                )
        else:
            # 未指定课程：校验该学生是否选修了当前教师授课的任意课程
            taught_course_ids = session.exec(
                select(Course.course_id).where(Course.teacher_id == teacher.teacher_id)
            ).all()
            if not taught_course_ids:
                raise HTTPException(
                    status_code=403,
                    detail="您当前未教授任何课程，无法查看学情画像",
                )
            enrollment = session.exec(
                select(CourseStudent).where(
                    CourseStudent.student_id == student_id,
                    CourseStudent.course_id.in_(taught_course_ids),  # type: ignore[arg-type]
                )
            ).first()
            if not enrollment:
                raise HTTPException(
                    status_code=403,
                    detail="该学生未选修您授课的课程，无法查看学情画像",
                )
        return

    # 其他未授权角色
    raise HTTPException(status_code=403, detail="无权查看学情画像")


def _check_course_access(
    session: Session,
    current_user: SysUser,
    course_id: int,
) -> None:
    """校验课程级数据查看权限（Analysis.ScoreTrend.UserValid）。

    - 任课教师（teacher）：仅可查看自己授课课程的数据
    - 学生（student）：无权查看班级/课程级分析数据
    - 管理员（admin）：不参与课程分析
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if role_code == "teacher":
        teacher = session.exec(
            select(Teacher).where(Teacher.user_id == current_user.user_id)
        ).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="当前账号未关联教师信息")
        if course.teacher_id != teacher.teacher_id:
            raise HTTPException(
                status_code=403,
                detail=f"仅授课教师可查看课程「{course.course_name}」的分析数据",
            )
        return

    raise HTTPException(status_code=403, detail="无权查看课程分析数据")


@router.get("/analysis/profile", tags=["学情分析"])
def get_student_profile(
    student_id: int = Query(...),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict | None:
    """获取学情画像。

    权限（Analysis.Profile.UserValid）：
    - 任课教师仅可查看自己授课课程内的学生画像
    - 学生仅可查看自己的画像
    """
    _check_profile_access(current_user, student_id, course_id, session)

    stmt = select(StudentProfile).where(StudentProfile.student_id == student_id)
    if course_id:
        stmt = stmt.where(StudentProfile.course_id == course_id)
    profile = session.exec(stmt).first()
    if not profile:
        return None

    student = session.get(Student, student_id)
    course = session.get(Course, profile.course_id)
    cls = session.get(ClassInfo, student.class_id) if student else None

    # 获取维度得分
    eval_result = session.exec(
        select(StudentEvaluationResult).where(
            StudentEvaluationResult.student_id == student_id,
            StudentEvaluationResult.course_id == profile.course_id,
        )
    ).first()

    dim_scores = []
    if eval_result:
        ds = session.exec(
            select(EvalDimensionScore).where(EvalDimensionScore.eval_id == eval_result.eval_id)
        ).all()
        for d in ds:
            dim_scores.append({"name": f"维度{d.dimension_id}", "score": d.dimension_score})

    tags = [t.strip() for t in (profile.study_tags or "").split(",") if t.strip()]

    return {
        "studentId": student_id,
        "studentNo": student.student_no if student else "",
        "studentName": student.real_name if student else "",
        "className": cls.class_name if cls else "",
        "courseName": course.course_name if course else "",
        "tags": tags,
        "radarValues": [
            profile.academic_score,
            profile.attitude_score,
            profile.progress_score,
            dim_scores[0]["score"] if dim_scores else 0,
            dim_scores[1]["score"] if len(dim_scores) > 1 else 0,
        ],
        "dimensionScores": dim_scores,
        "strongPoints": profile.good_modules or "",
        "weakPoints": profile.weak_modules or "",
    }


@router.get("/analysis/knowledge-heatmap", tags=["学情分析"])
def get_knowledge_heatmap(
    course_id: int = Query(...),
    class_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """获取知识点热力图数据（Analysis.Knowledge）。

    支持班级整体与个人两种视角（Analysis.Knowledge.Compare），
    返回每知识点掌握分数、等级、模块归属、薄弱清单。

    权限（Analysis.Knowledge.UserValid）：
    - 对应课程授课教师可查看班级数据
    - 学生仅可查看自己的热力图
    """
    # 按角色分流权限：学生走自助查询，教师走课程校验
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "student":
        student_rec = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not student_rec:
            raise HTTPException(status_code=403, detail="当前账号未关联学生信息")
        if student_id and student_id != student_rec.student_id:
            raise HTTPException(status_code=403, detail="学生仅可查看自己的知识点热力图")
        student_id = student_rec.student_id
    else:
        _check_course_access(session, current_user, course_id)

    # 获取该课程的知识模块与知识点
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_ids = [m.module_id for m in modules]
    module_map = {m.module_id: m.module_name for m in modules}
    point_module_map: dict[int, int] = {}  # point_id → module_id

    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all() if module_ids else []
    for p in points:
        point_module_map[p.point_id] = p.module_id

    kp_names = [p.point_name for p in points]
    kp_ids = [p.point_id for p in points]

    if not kp_names:
        return {
            "knowledgePoints": [], "students": [], "data": [], "levels": [],
            "pointMeta": [], "moduleSummary": [],
            "weakPoints": [], "weakModules": [],
            "levelLabels": {"1": "薄弱", "2": "一般", "3": "良好"},
        }

    # 获取该课程/班级的学生
    if student_id:
        student_ids = [student_id]
    else:
        stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
        if class_id:
            stu_in_class = session.exec(
                select(Student.student_id).where(Student.class_id == class_id)
            ).all()
            stmt = stmt.where(CourseStudent.student_id.in_(stu_in_class))  # type: ignore
        student_ids = session.exec(stmt).all()

    # 个人视图包含自主练习；班级视图只展示教师任务，避免自主练习污染班级统计。
    if role_code == "student":
        all_masteries = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.course_id == course_id,
                KnowledgeMastery.student_id.in_(student_ids),  # type: ignore
            )
        ).all()
        mastery_index = {
            (mastery.student_id, mastery.point_id): mastery.mastery_score
            for mastery in all_masteries
        }
    else:
        mastery_index = compute_mastery_index_with_fallback(session, course_id, student_ids)

    student_names = []
    for sid in student_ids:
        student = session.get(Student, sid)
        student_names.append(student.real_name if student else "?")

    # 辅助：score → (level_code, level_label)
    def score_level(s: float) -> tuple[int, str]:
        if s >= 80:
            return 3, "良好"
        if s >= 60:
            return 2, "一般"
        return 1, "薄弱"

    # 构建 ECharts heatmap data + levels（student_idx 按 student_ids 顺序）
    data: list[list] = []
    levels: list[list] = []
    for sid_idx, sid in enumerate(student_ids):
        for kp_idx, kpid in enumerate(kp_ids):
            score = mastery_index.get((sid, kpid), 0.0)
            level_code, _ = score_level(score)
            data.append([kp_idx, sid_idx, score])
            levels.append([kp_idx, sid_idx, level_code])

    # 班级平均（基于课程/班级全部学生，不受 student_id 筛选影响）
    # 获取用于计算班级平均的全体学生
    avg_stmt = select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
    if class_id:
        avg_in_class = session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all()
        avg_stmt = avg_stmt.where(CourseStudent.student_id.in_(avg_in_class))  # type: ignore
    avg_student_ids = session.exec(avg_stmt).all()

    avg_index = compute_mastery_index_with_fallback(session, course_id, avg_student_ids)

    class_avg: list[float] = []
    for kp_idx, kpid in enumerate(kp_ids):
        vals = [avg_index.get((sid, kpid), 0.0) for sid in avg_student_ids]
        class_avg.append(round(sum(vals) / len(vals), 1) if vals else 0)

    # ── 新增字段 ──

    # pointMeta：每知识点的元信息（Analysis.Knowledge.Module）
    point_meta = []
    for kp_idx, pt in enumerate(points):
        mid = point_module_map.get(pt.point_id)
        point_meta.append({
            "index": kp_idx,
            "pointId": pt.point_id,
            "pointName": pt.point_name,
            "moduleId": mid,
            "moduleName": module_map.get(mid, "") if mid else "",
            "classAvg": class_avg[kp_idx] if kp_idx < len(class_avg) else 0,
            "level": score_level(class_avg[kp_idx])[1] if kp_idx < len(class_avg) else "薄弱",
        })

    # moduleSummary：模块整体掌握度（Analysis.Knowledge.Module）
    module_scores: dict[int, list[float]] = {}
    for kp_idx, pt in enumerate(points):
        mid = point_module_map.get(pt.point_id)
        if mid is not None:
            module_scores.setdefault(mid, []).append(class_avg[kp_idx] if kp_idx < len(class_avg) else 0)
    module_summary = []
    for mid, scs in module_scores.items():
        avg = round(sum(scs) / len(scs), 1) if scs else 0
        level_label = score_level(avg)[1]
        module_summary.append({
            "moduleId": mid,
            "moduleName": module_map.get(mid, ""),
            "avgScore": avg,
            "level": level_label,
            "weakCount": sum(1 for s in scs if s < 60),
        })

    # weakPoints：班级薄弱知识点（classAvg < 60）
    weak_points = [
        {
            "pointName": pt.point_name,
            "moduleName": module_map.get(point_module_map.get(pt.point_id), ""),
            "classAvg": class_avg[kp_idx] if kp_idx < len(class_avg) else 0,
        }
        for kp_idx, pt in enumerate(points)
        if kp_idx < len(class_avg) and class_avg[kp_idx] < 60
    ]

    # weakModules：模块整体薄弱（module avg < 60）
    weak_modules = [
        m for m in module_summary if m["avgScore"] < 60
    ]

    # studentDetail：个人视角时的逐知识点对比详情（Analysis.Knowledge.Compare）
    student_detail = None
    if student_id and len(student_ids) == 1:
        student_detail = []
        for kp_idx, pt in enumerate(points):
            score = mastery_index.get((student_id, pt.point_id), 0.0)
            level_code, level_label = score_level(score)
            avg = class_avg[kp_idx] if kp_idx < len(class_avg) else 0
            student_detail.append({
                "pointId": pt.point_id,
                "pointName": pt.point_name,
                "moduleName": module_map.get(point_module_map.get(pt.point_id), ""),
                "score": score,
                "level": level_label,
                "levelCode": level_code,
                "classAvg": avg,
                "gap": round(score - avg, 1),
            })

    return {
        "knowledgePoints": kp_names,
        "students": student_names,
        "data": data,
        "classAvgByKp": class_avg,
        # 新增
        "levels": levels,
        "pointMeta": point_meta,
        "moduleSummary": module_summary,
        "weakPoints": weak_points,
        "weakModules": weak_modules,
        "studentDetail": student_detail,
        "levelLabels": {"1": "薄弱", "2": "一般", "3": "良好"},
    }


def _parse_warning_type(raw_type: str) -> tuple[str, str]:
    """解析 warning_type 字段为 (规则码, 显示文本)。

    - 自动扫描格式: "W1:实验报告较上次下滑 17.0 分" → ("W1", "实验报告较上次下滑 17.0 分")
    - 种子数据格式:  "成绩下滑"                  → ("W1", "成绩下滑")
    """
    if raw_type and raw_type[0] == "W" and ":" in raw_type:
        rule, display = raw_type.split(":", 1)
        return rule.strip(), display.strip()
    # 种子数据匹配
    type_rule_map = {
        "成绩下滑": "W1", "成绩暴跌": "W2", "缺勤超标": "W3",
        "作业未提交": "W4", "薄弱": "W5",
    }
    for key, rule in type_rule_map.items():
        if key in (raw_type or ""):
            return rule, raw_type
    return "", raw_type or ""


def _warning_response(w, student, course, cls) -> dict:
    """将 StudyWarning 模型转为 API 响应格式。"""
    rule_code, display_type = _parse_warning_type(w.warning_type)
    level_label = {1: "低", 2: "中", 3: "高"}.get(w.warning_level, "低")
    status_label = {0: "未处理", 1: "已处理"}.get(w.handle_status, "未知")

    return {
        "id": w.warning_id,
        "studentDbId": w.student_id,                          # 数据库 student_id（可用于跳转画像）
        "studentId": student.student_no if student else "",   # 学号（兼容旧字段）
        "studentName": student.real_name if student else "",
        "className": cls.class_name if cls else "",
        "classId": student.class_id if student else 0,
        "courseId": w.course_id,
        "courseName": course.course_name if course else "",
        "rule": rule_code,                # W1/W2/W3/W4/W5（Analysis.Warning.Rule）
        "type": display_type,             # 清理后的显示文本
        "level": level_label,             # 高/中/低（Analysis.Warning.Level）
        "levelCode": w.warning_level,     # 1/2/3
        "reason": w.warning_reason,
        "warningTime": w.create_time.strftime("%Y-%m-%d %H:%M") if w.create_time else "",
        "status": w.handle_status,
        "statusLabel": status_label,      # 未处理/已处理
    }


@router.get("/analysis/warnings", tags=["学情分析"])
def get_warnings(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    level: str | None = Query(default=None, description="高/中/低"),
    student_id: int | None = Query(default=None, description="按数据库 student_id 筛选"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """获取预警记录列表（Analysis.Warning.List）。

    权限（Analysis.Warning.UserValid）：
    - 任课教师仅可查看自己授课课程的预警
    - 学生无权查看
    - 管理员不参与教学预警
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    if role_code == "teacher":
        # 教师：限定只看自己授课课程的预警
        teacher = session.exec(
            select(Teacher).where(Teacher.user_id == current_user.user_id)
        ).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="当前账号未关联教师信息")
        taught_ids = session.exec(
            select(Course.course_id).where(Course.teacher_id == teacher.teacher_id)
        ).all()
        if course_id:
            if course_id not in taught_ids:
                raise HTTPException(
                    status_code=403,
                    detail="仅授课教师可查看该课程的预警数据",
                )
        else:
            # 未指定课程时自动限定为教师授课课程
            if not taught_ids:
                return []
    else:
        raise HTTPException(status_code=403, detail="无权查看预警数据")

    # 构建查询
    stmt = select(StudyWarning)
    if course_id:
        stmt = stmt.where(StudyWarning.course_id == course_id)
    elif role_code == "teacher":
        stmt = stmt.where(StudyWarning.course_id.in_(taught_ids))  # type: ignore[arg-type]
    if student_id:
        stmt = stmt.where(StudyWarning.student_id == student_id)

    warnings = session.exec(stmt).all()

    result = []
    for w in warnings:
        student = session.get(Student, w.student_id)
        course = session.get(Course, w.course_id)
        cls = session.get(ClassInfo, student.class_id) if student else None

        if class_id and (not student or student.class_id != class_id):
            continue
        if level:
            level_map = {1: "低", 2: "中", 3: "高"}
            if level_map.get(w.warning_level) != level:
                continue

        result.append(_warning_response(w, student, course, cls))

    return result


@router.post("/analysis/warnings/refresh", tags=["学情分析"])
def refresh_warnings(
    course_id: int = Query(...),
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """手动刷新课程预警列表（Analysis.Warning）。

    重新扫描课程内所有学生的成绩、考勤、作业、知识点数据，
    匹配 W1-W5 五条预警规则，覆盖更新预警记录。

    权限（Analysis.Warning.UserValid）：仅课程授课教师可操作。
    """
    _check_course_access(session, current_user, course_id)

    results = scan_course_warnings(session, course_id, class_id)
    count = persist_warnings(session, results, course_id)

    course = session.get(Course, course_id)
    return {
        "courseId": course_id,
        "courseName": course.course_name if course else "",
        "studentsScanned": len(results),
        "warningsCreated": count,
        "message": f"扫描完成：{len(results)} 名学生命中预警规则，共生成 {count} 条预警记录",
    }


@router.get("/analysis/grade-predictions", tags=["学情分析"])
def get_grade_predictions(
    course_id: int = Query(...),
    class_id: int = Query(...),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """成绩预测列表（一元线性回归，Analysis.ScoreTrend.Predict）。

    基于 predict.py 的 simple_linear_regression：
    - 对每位学生按历次考试时间拟合回归直线
    - 预测下一次考试成绩区间（95% 置信区间）
    - R² 反映拟合质量，数据点 ≥ 3 时回归有效，否则降级

    权限（Analysis.ScoreTrend.UserValid）：仅该课程授课教师可查看。
    """
    _check_course_access(session, current_user, course_id)

    # 课程内选修学生
    stmt = select(CourseStudent).where(CourseStudent.course_id == course_id)
    enrollments = session.exec(stmt).all()
    student_ids = [e.student_id for e in enrollments]

    # 只保留该班级学生
    class_students = session.exec(
        select(Student.student_id).where(Student.class_id == class_id)
    ).all()
    class_set = set(class_students)
    student_ids = [s for s in student_ids if s in class_set]

    result = []
    for sid in student_ids:
        student = session.get(Student, sid)
        if not student:
            continue

        pred = predict_student_scores(session, sid, course_id)

        result.append({
            "studentId": sid,
            "name": student.real_name,
            "studentNo": student.student_no,
            "current": pred["current"],
            "predicted": pred["predicted"],
            "predictedLow": pred["predicted_low"],
            "predictedHigh": pred["predicted_high"],
            "trend": pred["trend"],
            "confidence": pred["confidence"],
            "slope": pred["slope"],
            "rSquared": pred["r_squared"],
            "degraded": pred["degraded"],
            "history": pred["history"],
        })

    return result


@router.get("/analysis/grade-distribution", tags=["学情分析"])
def get_grade_distribution(
    course_id: int = Query(...),
    class_id: int | None = Query(default=None),
    batch_id: int | None = Query(default=None, description="指定考核批次ID，不传则汇总全部批次"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """成绩分布分析与班级特征识别（Analysis.ScoreTrend.Distribute）。

    返回：
    - distribution: 0-100 按 10 分一档的人数与占比（用于直方图）
    - statistics: 均值/中位数/标准差/极值/及格率/优秀率/不及格率
    - characteristic: 偏态描述 + 离散度描述（班级成绩形态特征）

    权限（Analysis.ScoreTrend.UserValid）：仅该课程授课教师可查看。
    """
    _check_course_access(session, current_user, course_id)

    scores: list[float] = []

    # 旧表 ScoreRecord
    stmt = select(ScoreRecord).where(ScoreRecord.course_id == course_id)
    if batch_id:
        stmt = stmt.where(ScoreRecord.batch_id == batch_id)
    if class_id:
        class_student_ids = session.exec(
            select(Student.student_id).where(Student.class_id == class_id)
        ).all()
        if class_student_ids:
            stmt = stmt.where(ScoreRecord.student_id.in_(class_student_ids))  # type: ignore[arg-type]
    for r in session.exec(stmt).all():
        scores.append(r.score)

    # 新表：获取 course 相关的 batch_ids
    course_batch_ids = session.exec(
        select(ExamBatch.batch_id).where(ExamBatch.course_id == course_id)
    ).all()

    # IndividualScore
    if course_batch_ids:
        is_stmt = select(IndividualScore).where(IndividualScore.exam_batch_id.in_(course_batch_ids))  # type: ignore[arg-type]
        if batch_id:
            is_stmt = select(IndividualScore).where(IndividualScore.exam_batch_id == batch_id)
        if class_id:
            class_student_ids = session.exec(
                select(Student.student_id).where(Student.class_id == class_id)
            ).all()
            if class_student_ids:
                is_stmt = is_stmt.where(IndividualScore.student_id.in_(class_student_ids))  # type: ignore[arg-type]
        for r in session.exec(is_stmt).all():
            scores.append(r.score)

        # CourseTestDetail
        ct_stmt = select(CourseTestDetail).where(CourseTestDetail.exam_batch_id.in_(course_batch_ids))  # type: ignore[arg-type]
        if batch_id:
            ct_stmt = select(CourseTestDetail).where(CourseTestDetail.exam_batch_id == batch_id)
        if class_id:
            if class_student_ids:
                ct_stmt = ct_stmt.where(CourseTestDetail.student_id.in_(class_student_ids))  # type: ignore[arg-type]
        for r in session.exec(ct_stmt).all():
            scores.append(r.total_score)

    if not scores:
        return {
            "distribution": [],
            "statistics": {},
            "characteristic": "暂无成绩数据",
        }

    n = len(scores)
    mean = sum(scores) / n
    sorted_scores = sorted(scores)
    mid = n // 2
    median = sorted_scores[mid] if n % 2 else (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
    variance = sum((s - mean) ** 2 for s in scores) / n
    std_dev = variance ** 0.5

    # 10 分一档直方图分布
    buckets = []
    for low in range(0, 100, 10):
        high = low + 9 if low < 90 else 100
        count = sum(1 for s in scores if low <= s <= high)
        buckets.append({
            "range": f"{low}-{high}",
            "low": low,
            "high": high,
            "count": count,
            "ratio": round(count / n * 100, 1),
        })

    # 基础统计
    pass_rate = sum(1 for s in scores if s >= 60) / n * 100
    excellent_rate = sum(1 for s in scores if s >= 90) / n * 100
    fail_rate = sum(1 for s in scores if s < 60) / n * 100

    # 偏度（识别成绩形态）
    skew = sum((s - mean) ** 3 for s in scores) / n / (std_dev ** 3) if std_dev > 0 else 0

    if skew > 0.5:
        skew_desc = "正偏态（高分段人数较多，整体偏右）"
    elif skew < -0.5:
        skew_desc = "负偏态（低分段人数较多，整体偏左）"
    else:
        skew_desc = "近似正态分布"

    # 离散度
    if std_dev < 8:
        dispersion = "集中（成绩差异小，学生水平趋同）"
    elif std_dev > 18:
        dispersion = "分散（成绩两极分化明显）"
    else:
        dispersion = "适中"

    characteristic = f"{skew_desc}，离散度{dispersion}"

    return {
        "distribution": buckets,
        "statistics": {
            "count": n,
            "mean": round(mean, 1),
            "median": round(median, 1),
            "stdDev": round(std_dev, 1),
            "maxScore": int(max(scores)),
            "minScore": int(min(scores)),
            "passRate": round(pass_rate, 1),
            "excellentRate": round(excellent_rate, 1),
            "failRate": round(fail_rate, 1),
            "skewness": round(skew, 2),
        },
        "characteristic": characteristic,
    }
