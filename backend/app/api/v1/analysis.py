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
)

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

    - 管理员（admin）：可查看所有学生画像
    - 任课教师（teacher）：仅可查看自己授课课程内的学生画像
    - 学生（student）：仅可查看自己的画像
    """
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""

    # 管理员：全部放行
    if role_code == "admin":
        return

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


@router.get("/analysis/profile", tags=["学情分析"])
def get_student_profile(
    student_id: int = Query(...),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict | None:
    """获取学情画像。

    权限（Analysis.Profile.UserValid）：
    - 管理员可查看所有学生画像
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
) -> dict:
    """获取知识点热力图数据。"""
    # 获取该课程的知识点
    modules = session.exec(
        select(KnowledgeModule).where(KnowledgeModule.course_id == course_id)
    ).all()
    module_ids = [m.module_id for m in modules]
    points = session.exec(
        select(KnowledgePoint).where(KnowledgePoint.module_id.in_(module_ids))  # type: ignore
    ).all() if module_ids else []
    kp_names = [p.point_name for p in points]
    kp_ids = [p.point_id for p in points]

    if not kp_names:
        return {"knowledgePoints": [], "students": [], "data": []}

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

    students_data = []
    student_names = []
    for sid in student_ids:
        student = session.get(Student, sid)
        if not student:
            continue
        student_names.append(student.real_name)
        row = []
        for kp_idx, kpid in enumerate(kp_ids):
            mastery = session.exec(
                select(KnowledgeMastery).where(
                    KnowledgeMastery.course_id == course_id,
                    KnowledgeMastery.student_id == sid,
                    KnowledgeMastery.point_id == kpid,
                )
            ).first()
            row.append(kp_idx)
            row.append(sid)
            row.append(mastery.mastery_score if mastery else 0)
            students_data.append(row)
            row = []  # reset for next point

    # 重新构建 data
    data = []
    for sid_idx, sid in enumerate(student_ids):
        for kp_idx, kpid in enumerate(kp_ids):
            mastery = session.exec(
                select(KnowledgeMastery).where(
                    KnowledgeMastery.course_id == course_id,
                    KnowledgeMastery.student_id == sid,
                    KnowledgeMastery.point_id == kpid,
                )
            ).first()
            data.append([kp_idx, sid_idx, mastery.mastery_score if mastery else 0])

    # 班级平均
    class_avg = []
    for kp_idx in range(len(kp_ids)):
        vals = [d[2] for d in data if d[0] == kp_idx]
        class_avg.append(round(sum(vals) / len(vals), 1) if vals else 0)

    return {
        "knowledgePoints": kp_names,
        "students": student_names,
        "data": data,
        "classAvgByKp": class_avg,
    }


@router.get("/analysis/warnings", tags=["学情分析"])
def get_warnings(
    course_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    level: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[dict]:
    """获取预警记录。"""
    stmt = select(StudyWarning)
    if course_id:
        stmt = stmt.where(StudyWarning.course_id == course_id)
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

        result.append({
            "id": w.warning_id,
            "studentId": student.student_no if student else "",
            "studentName": student.real_name if student else "",
            "className": cls.class_name if cls else "",
            "classId": student.class_id if student else 0,
            "deptId": 0,
            "courseId": w.course_id,
            "courseName": course.course_name if course else "",
            "semesterId": 0,
            "type": w.warning_type,
            "level": {1: "低", 2: "中", 3: "高"}.get(w.warning_level, "低"),
            "reason": w.warning_reason,
            "warningTime": w.create_time.strftime("%Y-%m-%d") if w.create_time else "",
            "status": w.handle_status,
        })

    return result


@router.get("/analysis/grade-predictions", tags=["学情分析"])
def get_grade_predictions(
    course_id: int = Query(...),
    class_id: int = Query(...),
    session: Session = Depends(get_session),
) -> list[dict]:
    """成绩预测列表（基于当前掌握度推算）。"""
    stmt = select(CourseStudent).where(CourseStudent.course_id == course_id)
    enrollments = session.exec(stmt).all()
    student_ids = [e.student_id for e in enrollments]

    # 只保留该班级学生
    class_students = session.exec(
        select(Student.student_id).where(Student.class_id == class_id)
    ).all()
    student_ids = [s for s in student_ids if s in set(class_students)]

    result = []
    for sid in student_ids:
        student = session.get(Student, sid)
        if not student:
            continue

        masteries = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.course_id == course_id,
                KnowledgeMastery.student_id == sid,
            )
        ).all()

        current = round(sum(m.mastery_score for m in masteries) / len(masteries)) if masteries else 70
        delta = 3 if current >= 85 else (0 if current >= 70 else -4)
        low = max(0, current + delta - 3)
        high = min(100, current + delta + 3)
        trend = "上升" if delta > 1 else ("下滑" if delta < -1 else "稳定")
        confidence = min(95, 70 + current // 5)

        result.append({
            "name": student.real_name,
            "current": current,
            "predicted": f"{low}-{high}",
            "trend": trend,
            "confidence": confidence,
        })

    return result
