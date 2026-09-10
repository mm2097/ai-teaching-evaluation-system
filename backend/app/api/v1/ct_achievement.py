"""课程目标达成度 API。

参照《计算机网络技术》教学大纲 CT1-CT8，为每位学生构建课程目标维度的个人画像。
端点：
  GET  /ct-achievement/definitions   CT1-CT8 定义 + 章节→CT 矩阵（前端展示用）
  GET  /ct-achievement/student       单学生 CT 达成度画像
  GET  /ct-achievement/class         班级 CT 达成度总览
  PUT  /ct-achievement/knowledge-ct  教师调整知识点→CT 映射
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    ClassInfo,
    Course,
    CourseStudent,
    KnowledgeModule,
    KnowledgePoint,
    Student,
    SysRole,
    SysUser,
    Teacher,
    CTAchievement,
)
from app.services.ct_constants import (
    CHAPTER_CT_MAP,
    CT_CODES,
    CT_DEFINITIONS,
    parse_ct_field,
)
from app.services.ct_achievement import compute_class_ct, compute_student_ct

router = APIRouter()


# ============================================================================
# 权限校验（与 analysis.py 同口径）
# ============================================================================

def _check_course_access(
    session: Session, current_user: SysUser, course_id: int
) -> None:
    """校验课程级数据查看权限：教师仅看自己授课课程。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if role_code == "teacher":
        teacher = session.exec(
            select(Teacher).where(Teacher.user_id == current_user.user_id)
        ).first()
        if not teacher or course.teacher_id != teacher.teacher_id:
            raise HTTPException(
                status_code=403,
                detail=f"仅授课教师可查看课程「{course.course_name}」的达成度数据",
            )
        return
    if role_code == "admin":
        return
    raise HTTPException(status_code=403, detail="无权查看课程目标达成度")


def _check_profile_access(
    current_user: SysUser, student_id: int, course_id: int, session: Session
) -> None:
    """校验学生画像查看权限：学生仅看自己，教师看授课课程内学生。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""
    target = session.get(Student, student_id)
    if not target:
        raise HTTPException(status_code=404, detail="学生不存在")

    if role_code == "student":
        me = session.exec(
            select(Student).where(Student.user_id == current_user.user_id)
        ).first()
        if not me or me.student_id != student_id:
            raise HTTPException(status_code=403, detail="学生仅可查看自己的达成度画像")
        return
    if role_code == "teacher":
        _check_course_access(session, current_user, course_id)
        # 校验该学生是否选修了该课程
        enrolled = session.exec(
            select(CourseStudent).where(
                CourseStudent.student_id == student_id,
                CourseStudent.course_id == course_id,
            )
        ).first()
        if not enrolled:
            raise HTTPException(status_code=403, detail="该学生未选修此课程")
        return
    if role_code == "admin":
        return
    raise HTTPException(status_code=403, detail="无权查看学生达成度画像")


# ============================================================================
# 端点
# ============================================================================

@router.get("/ct-achievement/definitions")
def get_ct_definitions(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
):
    """CT1-CT8 定义 + 章节→CT 矩阵 + 考核方式说明（前端展示用，无需课程权限）。"""
    return {
        "ct_codes": CT_CODES,
        "ct_definitions": CT_DEFINITIONS,
        "chapter_ct_map": CHAPTER_CT_MAP,
        "categories": [
            {"key": "知识", "cts": ["CT1", "CT2", "CT3"]},
            {"key": "能力", "cts": ["CT4", "CT5", "CT6"]},
            {"key": "素养", "cts": ["CT7", "CT8"]},
        ],
        "assessment_method": "总成绩 = 平时(30%) + 实践(30%) + 期末(40%)",
    }


@router.get("/ct-achievement/student")
def get_student_ct(
    student_id: int = Query(..., description="学生 ID"),
    course_id: int = Query(..., description="课程 ID"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
):
    """单学生 CT1-CT8 达成度画像。

    优先读已落库的 ct_achievement（分析刷新时计算）；无落库记录时实时计算。
    """
    _check_profile_access(current_user, student_id, course_id, session)

    # 优先读库
    row = session.exec(
        select(CTAchievement).where(
            CTAchievement.course_id == course_id,
            CTAchievement.student_id == student_id,
        )
    ).first()
    if row:
        return _row_to_student_response(row, session)

    # 实时计算
    result = compute_student_ct(session, student_id, course_id)
    stu = session.get(Student, student_id)
    resp = result.to_dict()
    resp["student_id"] = student_id
    resp["name"] = stu.real_name if stu else ""
    resp["student_no"] = stu.student_no if stu else ""
    resp["course_id"] = course_id
    return resp


@router.get("/ct-achievement/class")
def get_class_ct(
    course_id: int = Query(..., description="课程 ID"),
    class_id: int = Query(0, description="班级 ID，0=全部班级"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
):
    """班级 CT 达成度总览（雷达图 + 达成率柱状图 + 学生列表）。"""
    _check_course_access(session, current_user, course_id)
    cid = class_id if class_id else None
    return compute_class_ct(session, course_id, class_id=cid)


@router.put("/ct-achievement/knowledge-ct")
def update_knowledge_ct(
    point_id: int = Query(..., description="知识点 ID"),
    course_objectives: str = Query(..., description='课程目标编号，逗号分隔，如 "CT1,CT2,CT4"'),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
):
    """教师调整知识点的课程目标映射。

    调整后需手动触发分析刷新（或在数据管理页重新计算）使达成度重算。
    """
    # 校验：教师只能改自己课程的知识点
    point = session.get(KnowledgePoint, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")
    module = session.get(KnowledgeModule, point.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="知识模块不存在")
    _check_course_access(session, current_user, module.course_id)

    # 校验 CT 编号合法
    cts = parse_ct_field(course_objectives)
    if not cts and course_objectives.strip():
        raise HTTPException(status_code=400, detail="课程目标编号格式错误，应为 CT1-CT8 逗号分隔")

    point.course_objectives = ",".join(cts) if cts else None
    session.add(point)
    session.commit()
    return {"point_id": point_id, "course_objectives": point.course_objectives}


# ============================================================================
# 辅助
# ============================================================================

def _row_to_student_response(row: CTAchievement, session: Session) -> dict:
    """ct_achievement 落库行 → 前端响应结构（与 compute_student_ct.to_dict 同构）。"""
    from app.services.ct_constants import degree_to_level
    scores = {
        "CT1": row.ct1_score, "CT2": row.ct2_score, "CT3": row.ct3_score, "CT4": row.ct4_score,
        "CT5": row.ct5_score, "CT6": row.ct6_score, "CT7": row.ct7_score, "CT8": row.ct8_score,
    }
    # 解析置信度串（顺序 CT1-8）
    conf_list = (row.ct_confidence or "").split(",")
    conf_map = {ct: (conf_list[i].strip() if i < len(conf_list) and conf_list[i].strip() else None)
                for i, ct in enumerate(CT_CODES)}
    weak = [c for c in (row.weak_cts or "").split(",") if c.strip()]
    strong = [c for c in (row.strong_cts or "").split(",") if c.strip()]
    stu = session.get(Student, row.student_id)
    return {
        "student_id": row.student_id,
        "name": stu.real_name if stu else "",
        "student_no": stu.student_no if stu else "",
        "course_id": row.course_id,
        "ct_scores": {
            ct: {
                "score": scores[ct],
                "level": degree_to_level(scores[ct]) if scores[ct] is not None else None,
                "confidence": conf_map.get(ct),
                "desc": CT_DEFINITIONS[ct]["desc"],
                "category": CT_DEFINITIONS[ct]["category"],
            }
            for ct in CT_CODES
        },
        "overall": {"score": row.overall_score, "level": row.overall_level},
        "weak_cts": weak,
        "strong_cts": strong,
        "radar": {ct: scores[ct] for ct in CT_CODES},
    }
