"""教学数据接口：文件上传导入、聚合查询。

文件上传流程（对应需求规格说明书 3.2.6 节）：
  1. 登录验证（Data.FileUpload.UserValid）
  2. 权限验证：仅授课教师可上传（Data.FileUpload.UserValid.Logined）
  3. 格式校验：仅 .xlsx / UTF-8 逗号分隔 .txt（Data.FileUpload.Format）
  4. 表头字段校验（Data.FileUpload.Check）
  5. 返回导入结果 + 错误明细（Data.FileUpload.Result）
"""

import os
import tempfile
import uuid

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.operation_log import get_current_user
from app.models import (
    ScoreRecord, AttendanceRecord, Course, Student, CourseStudent,
    SysUser, Teacher, SysRole,
)
from app.services.file_import import import_file, ImportResult, TEMPLATE_META, generate_template_xlsx

router = APIRouter()

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".xlsx", ".txt"}


# ============================================================================
# 查询接口
# ============================================================================


@router.get("/teaching-data", tags=["教学数据"])
def get_teaching_data(session: Session = Depends(get_session)) -> list[dict]:
    """返回所有教学数据（成绩 + 考勤），供数据管理页面展示。"""
    result: list[dict] = []
    row_id = 1

    # 成绩记录
    scores = session.exec(select(ScoreRecord)).all()
    for s in scores:
        course = session.get(Course, s.course_id)
        student = session.get(Student, s.student_id)
        if not course or not student:
            continue
        result.append({
            "id": row_id,
            "dataType": "score",
            "studentId": student.student_no,
            "studentName": student.real_name,
            "courseId": course.course_code,
            "courseName": course.course_name,
            "semester": course.semester,
            "score": s.score,
            "attendance": None,
            "homework": None,
            "sourceFileName": "seed_data",
            "classId": student.class_id,
            "deptId": 1,
            "majorId": 0,
        })
        row_id += 1

    # 考勤记录
    attendances = session.exec(select(AttendanceRecord)).all()
    status_map = {0: "正常", 1: "迟到", 2: "早退", 3: "缺勤", 4: "请假"}
    for a in attendances:
        course = session.get(Course, a.course_id)
        student = session.get(Student, a.student_id)
        if not course or not student:
            continue
        result.append({
            "id": row_id,
            "dataType": "attendance",
            "studentId": student.student_no,
            "studentName": student.real_name,
            "courseId": course.course_code,
            "courseName": course.course_name,
            "semester": course.semester,
            "score": None,
            "attendance": status_map.get(a.status, "正常"),
            "homework": None,
            "sourceFileName": "seed_data",
            "classId": student.class_id,
            "deptId": 1,
            "majorId": 0,
        })
        row_id += 1

    return result


# ============================================================================
# 文件上传导入接口
# ============================================================================


@router.post("/teaching-data/upload", tags=["教学数据"])
def upload_teaching_data(
    file: UploadFile = File(...),
    course_id: int = Query(..., description="课程 ID"),
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """上传教学数据文件并批量导入。

    权限：必须登录，且为对应课程的任课教师。
    格式：仅 .xlsx / .txt（UTF-8 逗号分隔）。
    模板：自动检测匹配课程测试各题扣分情况 / 成绩汇总 / 成绩考勤情况。
    """
    # ------ 1. 登录验证（Data.FileUpload.UserValid）------
    if not current_user:
        raise HTTPException(status_code=401, detail="请先登录")

    # ------ 2. 文件格式校验（Data.FileUpload.Format）------
    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 .xlsx 和 UTF-8 逗号分隔 .txt 格式，当前文件扩展名为「{ext}」",
        )

    # ------ 3. 课程与权限校验（Data.FileUpload.UserValid.Logined）------
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    # 查找当前用户对应的教师记录
    teacher = session.exec(
        select(Teacher).where(Teacher.user_id == current_user.user_id)
    ).first()
    if not teacher:
        raise HTTPException(
            status_code=403,
            detail="仅任课教师可上传教学数据，当前账号未关联教师信息",
        )
    if course.teacher_id != teacher.teacher_id:
        raise HTTPException(
            status_code=403,
            detail=f"仅授课教师可上传数据。课程「{course.course_name}」的授课教师与当前账号不匹配",
        )

    # ------ 4. 保存临时文件 & 导入 ------
    tmp_path = os.path.join(
        tempfile.gettempdir(),
        f"teaching_data_upload_{uuid.uuid4().hex}{ext}",
    )
    try:
        content = file.file.read()
        # 对于 .txt 文件，校验 UTF-8 编码
        if ext == ".txt":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Txt 文件必须是 UTF-8 编码，当前文件编码不符",
                )

        with open(tmp_path, "wb") as f:
            f.write(content)

        # 调用导入服务
        result: ImportResult = import_file(
            session=session,
            file_path=tmp_path,
            file_ext=ext,
            course_id=course_id,
            create_by=current_user.user_id,
        )

    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ------ 5. 返回结果（Data.FileUpload.Result）------
    return {
        "fileName": file.filename,
        "courseId": course_id,
        "courseName": course.course_name,
        "detectedTemplate": result.detected_template,
        "sheetsProcessed": result.sheets_processed,
        "successCount": result.success_count,
        "errorCount": result.error_count,
        "errors": [
            {
                "sheet": e.sheet,
                "row": e.row,
                "field": e.field,
                "message": e.message,
            }
            for e in result.errors
        ],
    }


# ============================================================================
# 模板下载接口（3.2.5 节）
# ============================================================================

def _check_template_access(current_user: SysUser, session: Session) -> None:
    """校验模板下载权限：管理员或任课教师（Data.Template.UserValid）。"""
    role = session.get(SysRole, current_user.role_id)
    role_code = role.role_code if role else ""
    if role_code not in ("admin", "teacher"):
        raise HTTPException(
            status_code=403,
            detail="仅管理员和任课教师可下载模板",
        )


@router.get("/teaching-data/templates", tags=["教学数据"])
def list_templates(
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> list[dict]:
    """返回可下载的模板列表（Data.Template.Type）。

    按 dataType 分组：成绩、考勤。
    权限：管理员或任课教师。
    """
    _check_template_access(current_user, session)
    return [
        {
            "templateId": m["template_id"],
            "name": m["name"],
            "dataType": m["dataType"],
            "description": m["description"],
            "headers": m["headers"],
        }
        for m in TEMPLATE_META
    ]


@router.get("/teaching-data/templates/{template_id}", tags=["教学数据"])
def download_template(
    template_id: str,
    session: Session = Depends(get_session),
    current_user: SysUser = Depends(get_current_user),
) -> Response:
    """下载指定模板的 .xlsx 文件（Data.Template.Download）。

    返回标准模板文件，含表头、示例行、填写说明。
    权限：管理员或任课教师。
    """
    _check_template_access(current_user, session)

    meta = next((m for m in TEMPLATE_META if m["template_id"] == template_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")

    try:
        xlsx_bytes = generate_template_xlsx(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 文件名含中文，用 RFC 5987 编码
    safe_name = f"模板-{meta['name']}.xlsx"
    encoded = quote(safe_name, safe="")
    # ASCII 兜底文件名
    ascii_name = f"template-{template_id}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; "
                f"filename*=UTF-8''{encoded}"
            ),
        },
    )
