"""文件导入服务：检测模板、校验数据、批量导入教学数据。

支持的模板：
  1. 课程测试各题扣分情况 → ExamBatch + ScoreRecord
  2. 成绩汇总             → ExamBatch + ScoreRecord（按成绩类型拆分为多个批次）
  3. 成绩考勤情况         → AttendanceRecord
"""

from __future__ import annotations

import csv
import io
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import openpyxl
from sqlmodel import Session

from app.models import (
    AttendanceRecord,
    Course,
    CourseStudent,
    ExamBatch,
    ScoreRecord,
    Student,
    SysUser,
)


# ============================================================================
# 模板定义
# ============================================================================

@dataclass
class TemplateDef:
    """模板定义：用于匹配和导入。"""

    template_id: str
    name: str
    # 用于匹配的关键表头（只要这些字段全部存在，即命中模板）
    match_headers: list[str]
    # 所有可能的表头（包括可选字段）
    all_headers: list[str]
    # 必填字段列表（行数据中必须非空）
    required_fields: list[str]
    # 数字字段列表（用于类型校验）
    numeric_fields: list[str]


# 模板1：课程测试各题扣分情况
TEMPLATE_EXAM_DEDUCTION = TemplateDef(
    template_id="exam_deduction",
    name="课程测试各题扣分情况",
    match_headers=["学号", "第1大题", "第2大题", "总成绩"],
    all_headers=[
        "编号", "课程名称", "测试名称", "学号", "姓名",
        "第1大题", "第1大题扣分的主要知识点",
        "第2大题", "第2大题扣分的主要知识点",
        "第3大题", "第3大题扣分的主要知识点",
        "第4大题", "第4大题扣分的主要知识点",
        "第5大题", "第5大题扣分的主要知识点",
        "总成绩",
    ],
    required_fields=["学号", "姓名"],
    numeric_fields=["第1大题", "第2大题", "第3大题", "第4大题", "第5大题", "总成绩"],
)

# 模板2：成绩汇总（兼容简化版无课程名称/期末成绩/总评成绩的情况）
TEMPLATE_SCORE_SUMMARY = TemplateDef(
    template_id="score_summary",
    name="成绩汇总",
    match_headers=["学号", "期中成绩", "平时成绩1", "平时成绩2"],
    all_headers=[
        "编号", "课程名称", "学号", "姓名",
        "期中成绩", "课堂平时成绩", "作业成绩", "平时成绩1",
        "实验成绩", "小班讨论成绩", "课程设计", "平时成绩2",
        "期末成绩", "总评成绩",
    ],
    required_fields=["学号", "姓名"],
    numeric_fields=[
        "期中成绩", "课堂平时成绩", "作业成绩",
        "实验成绩", "小班讨论成绩", "课程设计",
        "期末成绩", "总评成绩",
    ],
)

# 模板3：成绩考勤情况
TEMPLATE_ATTENDANCE = TemplateDef(
    template_id="attendance",
    name="成绩考勤情况",
    match_headers=["学号", "考勤1", "考勤2", "考勤3"],
    all_headers=[
        "编号", "课程名称", "学号", "姓名",
        *[f"考勤{i}" for i in range(1, 33)],
        "考勤总数", "到课数", "请假数", "到课率",
    ],
    required_fields=["学号", "姓名"],
    numeric_fields=[],
)

# 模板4：简化成绩（仅含期中成绩等单列成绩）
TEMPLATE_SIMPLE_SCORE = TemplateDef(
    template_id="simple_score",
    name="简化成绩",
    match_headers=["学号", "期中成绩"],
    all_headers=["编号", "学号", "姓名", "期中成绩"],
    required_fields=["学号", "姓名"],
    numeric_fields=["期中成绩"],
)

ALL_TEMPLATES: list[TemplateDef] = [
    TEMPLATE_EXAM_DEDUCTION,
    TEMPLATE_SCORE_SUMMARY,
    TEMPLATE_ATTENDANCE,
    TEMPLATE_SIMPLE_SCORE,
]


# ============================================================================
# 结果与错误结构
# ============================================================================

@dataclass
class ImportError:
    """单条导入错误。"""

    sheet: str
    row: int
    field: str | None
    message: str


@dataclass
class ImportResult:
    """导入结果汇总。"""

    success_count: int = 0
    error_count: int = 0
    errors: list[ImportError] = field(default_factory=list)
    detected_template: str | None = None
    sheets_processed: list[str] = field(default_factory=list)


# ============================================================================
# 工具函数
# ============================================================================

def _is_formula(value: Any) -> bool:
    """判断是否为 Excel 公式（字符串以 = 开头）。"""
    return isinstance(value, str) and value.startswith("=")


def _safe_float(value: Any) -> float | None:
    """安全转换为 float，公式或非法值返回 None。"""
    if value is None:
        return None
    if _is_formula(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> int | None:
    """安全转换为 int。"""
    f = _safe_float(value)
    if f is not None:
        return int(f)
    return None


def _safe_str(value: Any) -> str | None:
    """安全转换为字符串。"""
    if value is None:
        return None
    if _is_formula(value):
        return None
    return str(value).strip()


def _normalize_headers(headers: list[str | None]) -> list[str]:
    """过滤 None 并去除首尾空格。"""
    return [h.strip() for h in headers if h is not None and str(h).strip()]


# ============================================================================
# 模板检测
# ============================================================================

def detect_template(headers: list[str]) -> TemplateDef | None:
    """根据表头检测匹配的模板。

    匹配逻辑：模板的 match_headers 全部存在于文件表头中即视为命中。
    若多个模板命中，取匹配数量最多的；平局时取第一个。
    """
    header_set = set(headers)
    best: tuple[TemplateDef, int] | None = None

    for tmpl in ALL_TEMPLATES:
        match_count = sum(1 for h in tmpl.match_headers if h in header_set)
        if match_count == len(tmpl.match_headers):
            if best is None or match_count > best[1]:
                best = (tmpl, match_count)

    return best[0] if best else None


# ============================================================================
# 行级校验
# ============================================================================

def validate_row(
    row_data: dict[str, Any],
    tmpl: TemplateDef,
    sheet_name: str,
    row_index: int,  # 1-based 数据行号（Excel 行号）
) -> list[ImportError]:
    """校验单行数据，返回错误列表。"""
    errors: list[ImportError] = []

    # 必填字段校验
    for field in tmpl.required_fields:
        if field not in row_data or row_data[field] is None or str(row_data[field]).strip() == "":
            errors.append(ImportError(
                sheet=sheet_name,
                row=row_index,
                field=field,
                message=f"必填字段「{field}」为空",
            ))

    # 数字字段校验
    for field in tmpl.numeric_fields:
        if field in row_data and row_data[field] is not None:
            val = row_data[field]
            if _is_formula(val):
                errors.append(ImportError(
                    sheet=sheet_name,
                    row=row_index,
                    field=field,
                    message=f"字段「{field}」包含公式，请上传前将公式转为数值",
                ))
            elif not isinstance(val, (int, float)):
                try:
                    float(val)
                except (ValueError, TypeError):
                    errors.append(ImportError(
                        sheet=sheet_name,
                        row=row_index,
                        field=field,
                        message=f"字段「{field}」应为数字，实际值为「{val}」",
                    ))

    # 学号字段校验（应为数字串或纯数字）
    student_no = str(row_data.get("学号", "")).strip()
    if student_no and not student_no.isdigit():
        errors.append(ImportError(
            sheet=sheet_name,
            row=row_index,
            field="学号",
            message=f"学号应为纯数字，实际值为「{student_no}」",
        ))

    return errors


# ============================================================================
# 文件解析
# ============================================================================

def _find_header_row(
    rows: list[tuple[Any, ...]],
) -> tuple[int, list[str], dict[int, str]]:
    """在 sheet 的前几行中寻找表头行。

    返回 (header_row_index, headers_list, col_index_to_name)。
    若找不到则 header_row_index=-1。
    """
    for ri in range(min(4, len(rows))):
        raw_headers = [str(c).strip() if c is not None else None for c in rows[ri]]
        headers = [h for h in raw_headers if h]
        if len(headers) >= 2:
            # 构建列索引 → 列名映射
            col_map: dict[int, str] = {}
            for ci, h in enumerate(raw_headers):
                if h:
                    col_map[ci] = h
            return ri, headers, col_map
    return -1, [], {}


def parse_xlsx(file_path: str) -> dict[str, list[dict[str, Any]]]:
    """解析 .xlsx 文件，返回 {sheet_name: [row_dict, ...], ...}。

    自动在前 4 行中寻找表头行（不再硬编码第1行）。
    忽略全空行；公式单元格保留字符串形式。
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    result: dict[str, list[dict[str, Any]]] = {}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        header_idx, headers, col_map = _find_header_row(rows)
        if header_idx < 0 or not headers:
            continue

        sheet_data: list[dict[str, Any]] = []
        for row_idx, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            row_dict: dict[str, Any] = {}
            all_none = True
            for col_idx, cell_value in enumerate(row):
                if col_idx in col_map:
                    header_name = col_map[col_idx]
                    row_dict[header_name] = cell_value
                if cell_value is not None:
                    all_none = False

            # 跳过全空行
            if all_none or not row_dict:
                continue
            # 跳过无身份标识的汇总/统计行：学号和姓名同时为空
            sno_val = row_dict.get("学号")
            name_val = row_dict.get("姓名")
            if (sno_val is None or str(sno_val).strip() == "") and \
               (name_val is None or str(name_val).strip() == ""):
                continue

            sheet_data.append({"_excel_row": row_idx, **row_dict})

        if sheet_data:
            result[sheet_name] = sheet_data

    wb.close()
    return result


def parse_txt(file_path: str) -> dict[str, list[dict[str, Any]]]:
    """解析逗号分隔的 UTF-8 .txt 文件，返回 {"default": [row_dict, ...]}。"""
    result: dict[str, list[dict[str, Any]]] = {}
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # 使用 csv 模块解析
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return result

    headers = _normalize_headers(rows[0])
    if not headers:
        return result

    sheet_data: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows[1:], start=2):
        row_dict: dict[str, Any] = {}
        all_empty = True
        for i, cell_value in enumerate(row):
            if i < len(headers):
                header_name = headers[i]
                val = cell_value.strip() if cell_value else None
                row_dict[header_name] = val
                if val:
                    all_empty = False

        # 跳过全空行
        if all_empty or not row_dict:
            continue
        # 跳过无身份标识的汇总/统计行：学号和姓名同时为空
        sno_val = row_dict.get("学号")
        name_val = row_dict.get("姓名")
        if (sno_val is None or str(sno_val).strip() == "") and \
           (name_val is None or str(name_val).strip() == ""):
            continue

        sheet_data.append({"_excel_row": row_idx, **row_dict})

    result["default"] = sheet_data
    return result


# ============================================================================
# 数据导入
# ============================================================================

def _get_or_create_exam_batch(
    session: Session,
    course_id: int,
    batch_name: str,
    batch_type: int,
    batch_weight: float | None,
    create_by: int,
) -> ExamBatch:
    """获取或创建考核批次。"""
    from sqlmodel import select

    stmt = select(ExamBatch).where(
        ExamBatch.course_id == course_id,
        ExamBatch.batch_name == batch_name,
    )
    batch = session.exec(stmt).first()
    if batch:
        return batch

    batch = ExamBatch(
        course_id=course_id,
        batch_name=batch_name,
        batch_type=batch_type,
        batch_weight=batch_weight,
        exam_time=datetime.now(),
        full_score=100,
        create_by=create_by,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def _get_student_by_no(session: Session, student_no: str) -> Student | None:
    """根据学号查找学生。"""
    from sqlmodel import select

    return session.exec(
        select(Student).where(Student.student_no == str(student_no).strip())
    ).first()


def _ensure_course_student(session: Session, course_id: int, student_id: int) -> None:
    """确保学生在课程选修表中存在。"""
    from sqlmodel import select

    exists = session.exec(
        select(CourseStudent).where(
            CourseStudent.course_id == course_id,
            CourseStudent.student_id == student_id,
        )
    ).first()
    if not exists:
        session.add(CourseStudent(
            course_id=course_id,
            student_id=student_id,
            status=1,
        ))
        session.commit()


def _import_exam_deduction(
    session: Session,
    sheet_data: dict[str, list[dict[str, Any]]],
    course_id: int,
    create_by: int,
    tmpl: TemplateDef,
) -> ImportResult:
    """导入模板1数据：课程测试各题扣分情况。"""
    result = ImportResult(detected_template=tmpl.name)

    for sheet_name, rows in sheet_data.items():
        result.sheets_processed.append(sheet_name)

        for row_data in rows:
            excel_row = row_data.get("_excel_row", 0)

            # 校验
            errors = validate_row(row_data, tmpl, sheet_name, excel_row)
            if errors:
                result.errors.extend(errors)
                result.error_count += len(errors)
                continue

            student_no = str(row_data.get("学号", "")).strip()
            student = _get_student_by_no(session, student_no)
            if not student:
                result.errors.append(ImportError(
                    sheet=sheet_name, row=excel_row, field="学号",
                    message=f"学号「{student_no}」在系统中不存在",
                ))
                result.error_count += 1
                continue

            _ensure_course_student(session, course_id, student.student_id)

            exam_name = str(row_data.get("测试名称") or "考试").strip()
            batch = _get_or_create_exam_batch(
                session, course_id, exam_name,
                batch_type=3,  # 期中/考试
                batch_weight=None,
                create_by=create_by,
            )

            # 总成绩：安全转浮点
            total_score = _safe_float(row_data.get("总成绩"))
            if total_score is None:
                total_score = 0.0

            # 检查是否已有成绩记录（去重）
            from sqlmodel import select
            existing = session.exec(
                select(ScoreRecord).where(
                    ScoreRecord.student_id == student.student_id,
                    ScoreRecord.batch_id == batch.batch_id,
                )
            ).first()
            if existing:
                existing.score = float(total_score)
                existing.update_time = datetime.now()
                session.add(existing)
            else:
                session.add(ScoreRecord(
                    course_id=course_id,
                    student_id=student.student_id,
                    batch_id=batch.batch_id,
                    score=float(total_score),
                    is_pass=1 if total_score >= 60 else 0,
                    create_by=create_by,
                ))
            session.commit()
            result.success_count += 1

    return result


def _import_score_summary(
    session: Session,
    sheet_data: dict[str, list[dict[str, Any]]],
    course_id: int,
    create_by: int,
    tmpl: TemplateDef,
) -> ImportResult:
    """导入模板2数据：成绩汇总。

    将各项成绩分别存入对应名称的 ExamBatch + ScoreRecord。
    """
    # 成绩列 → 批次名称/类型的映射
    SCORE_FIELD_MAP: dict[str, tuple[str, int, float | None]] = {
        "期中成绩":   ("期中考试", 3, 25),
        "期末成绩":   ("期末考试", 4, 50),
        "课堂平时成绩": ("课堂平时成绩", 1, None),
        "作业成绩":   ("作业成绩", 1, None),
        "实验成绩":   ("实验成绩", 2, None),
        "小班讨论成绩": ("小班讨论成绩", 1, None),
        "课程设计":   ("课程设计", 2, None),
    }

    result = ImportResult(detected_template=tmpl.name)

    for sheet_name, rows in sheet_data.items():
        result.sheets_processed.append(sheet_name)

        # 先为所有成绩类型创建 ExamBatch
        batches: dict[str, ExamBatch] = {}
        for field, (batch_name, batch_type, batch_weight) in SCORE_FIELD_MAP.items():
            batches[field] = _get_or_create_exam_batch(
                session, course_id, batch_name, batch_type, batch_weight, create_by,
            )

        for row_data in rows:
            excel_row = row_data.get("_excel_row", 0)

            # 跳过完全空行
            if not any(
                v is not None and str(v).strip() != ""
                for k, v in row_data.items()
                if k in SCORE_FIELD_MAP
            ):
                continue

            errors = validate_row(row_data, tmpl, sheet_name, excel_row)
            if errors:
                result.errors.extend(errors)
                result.error_count += len(errors)
                continue

            student_no = str(row_data.get("学号", "")).strip()
            student = _get_student_by_no(session, student_no)
            if not student:
                result.errors.append(ImportError(
                    sheet=sheet_name, row=excel_row, field="学号",
                    message=f"学号「{student_no}」在系统中不存在",
                ))
                result.error_count += 1
                continue

            _ensure_course_student(session, course_id, student.student_id)

            # 逐项成绩导入
            for field, batch in batches.items():
                score_val = _safe_float(row_data.get(field))
                if score_val is None:
                    continue  # 该项无成绩，跳过

                from sqlmodel import select
                existing = session.exec(
                    select(ScoreRecord).where(
                        ScoreRecord.student_id == student.student_id,
                        ScoreRecord.batch_id == batch.batch_id,
                    )
                ).first()
                if existing:
                    existing.score = float(score_val)
                    existing.is_pass = 1 if score_val >= 60 else 0
                    existing.update_time = datetime.now()
                    session.add(existing)
                else:
                    session.add(ScoreRecord(
                        course_id=course_id,
                        student_id=student.student_id,
                        batch_id=batch.batch_id,
                        score=float(score_val),
                        is_pass=1 if score_val >= 60 else 0,
                        create_by=create_by,
                    ))
                session.commit()

            result.success_count += 1

    return result


def _import_attendance(
    session: Session,
    sheet_data: dict[str, list[dict[str, Any]]],
    course_id: int,
    create_by: int,
    tmpl: TemplateDef,
) -> ImportResult:
    """导入模板3数据：成绩考勤情况。

    每条考勤记录创建一条 AttendanceRecord。
    考勤值映射：到→0(出勤), 缺→3(缺勤), 请假→4(请假), 迟到→1(迟到)
    """
    ATTENDANCE_MAP: dict[str, int] = {
        "到": 0, "正常": 0, "出勤": 0,
        "迟到": 1,
        "早退": 2,
        "缺": 3, "缺勤": 3, "旷课": 3,
        "请假": 4, "病假": 4, "事假": 4,
    }

    result = ImportResult(detected_template=tmpl.name)

    # 考勤日期基准 —— 取课程学期确定起始日期（简化处理：取当年9月或当前月）
    # 实际使用中，考勤1~32 对应课程的第1~32次课
    # 这里按序号存储，日期取当前导入日期
    base_date = date.today()

    for sheet_name, rows in sheet_data.items():
        result.sheets_processed.append(sheet_name)

        for row_data in rows:
            excel_row = row_data.get("_excel_row", 0)

            errors = validate_row(row_data, tmpl, sheet_name, excel_row)
            if errors:
                result.errors.extend(errors)
                result.error_count += len(errors)
                continue

            student_no = str(row_data.get("学号", "")).strip()
            student = _get_student_by_no(session, student_no)
            if not student:
                result.errors.append(ImportError(
                    sheet=sheet_name, row=excel_row, field="学号",
                    message=f"学号「{student_no}」在系统中不存在",
                ))
                result.error_count += 1
                continue

            _ensure_course_student(session, course_id, student.student_id)

            row_imported = 0
            for i in range(1, 33):
                col_name = f"考勤{i}"
                att_val = str(row_data.get(col_name, "")).strip() if row_data.get(col_name) else ""
                if not att_val:
                    continue

                status = ATTENDANCE_MAP.get(att_val)
                if status is None:
                    result.errors.append(ImportError(
                        sheet=sheet_name, row=excel_row, field=col_name,
                        message=f"无法识别的考勤值「{att_val}」，支持：到/缺/请假/迟到",
                    ))
                    result.error_count += 1
                    continue

                from sqlmodel import select
                existing = session.exec(
                    select(AttendanceRecord).where(
                        AttendanceRecord.course_id == course_id,
                        AttendanceRecord.student_id == student.student_id,
                        AttendanceRecord.attendance_date == base_date,
                    )
                ).first()

                if existing:
                    existing.status = status
                    existing.update_time = datetime.now()
                    session.add(existing)
                else:
                    session.add(AttendanceRecord(
                        course_id=course_id,
                        student_id=student.student_id,
                        attendance_date=base_date,
                        status=status,
                        create_by=create_by,
                    ))
                session.commit()
                row_imported += 1

            # 即使单条都没导入成功，也计一行
            if row_imported > 0:
                result.success_count += row_imported

    return result


# ============================================================================
# 导入调度
# ============================================================================

def _import_simple_score(
    session: Session,
    sheet_data: dict[str, list[dict[str, Any]]],
    course_id: int,
    create_by: int,
    tmpl: TemplateDef,
) -> ImportResult:
    """导入简化成绩：仅期中成绩列。

    格式：编号, 学号, 姓名, 期中成绩
    """
    result = ImportResult(detected_template=tmpl.name)

    batch = _get_or_create_exam_batch(
        session, course_id, "期中考试",
        batch_type=3, batch_weight=25, create_by=create_by,
    )

    for sheet_name, rows in sheet_data.items():
        result.sheets_processed.append(sheet_name)

        for row_data in rows:
            excel_row = row_data.get("_excel_row", 0)

            errors = validate_row(row_data, tmpl, sheet_name, excel_row)
            if errors:
                result.errors.extend(errors)
                result.error_count += len(errors)
                continue

            student_no = str(row_data.get("学号", "")).strip()
            student = _get_student_by_no(session, student_no)
            if not student:
                result.errors.append(ImportError(
                    sheet=sheet_name, row=excel_row, field="学号",
                    message=f"学号「{student_no}」在系统中不存在",
                ))
                result.error_count += 1
                continue

            _ensure_course_student(session, course_id, student.student_id)

            score_val = _safe_float(row_data.get("期中成绩"))
            if score_val is None:
                result.errors.append(ImportError(
                    sheet=sheet_name, row=excel_row, field="期中成绩",
                    message="期中成绩为空或格式错误",
                ))
                result.error_count += 1
                continue

            from sqlmodel import select
            existing = session.exec(
                select(ScoreRecord).where(
                    ScoreRecord.student_id == student.student_id,
                    ScoreRecord.batch_id == batch.batch_id,
                )
            ).first()
            if existing:
                existing.score = float(score_val)
                existing.is_pass = 1 if score_val >= 60 else 0
                existing.update_time = datetime.now()
                session.add(existing)
            else:
                session.add(ScoreRecord(
                    course_id=course_id,
                    student_id=student.student_id,
                    batch_id=batch.batch_id,
                    score=float(score_val),
                    is_pass=1 if score_val >= 60 else 0,
                    create_by=create_by,
                ))
            session.commit()
            result.success_count += 1

    return result


IMPORT_HANDLERS: dict[str, Callable] = {
    TEMPLATE_EXAM_DEDUCTION.template_id: _import_exam_deduction,
    TEMPLATE_SCORE_SUMMARY.template_id: _import_score_summary,
    TEMPLATE_ATTENDANCE.template_id: _import_attendance,
    TEMPLATE_SIMPLE_SCORE.template_id: _import_simple_score,
}


def import_file(
    session: Session,
    file_path: str,
    file_ext: str,
    course_id: int,
    create_by: int,
) -> ImportResult:
    """主导入流程：解析文件 → 按 Sheet 检测模板 → 校验 → 导入。

    每个 Sheet 独立检测模板并导入，同一文件可包含多种模板数据。
    """
    # 1. 解析文件
    if file_ext == ".xlsx":
        sheet_data = parse_xlsx(file_path)
    elif file_ext == ".txt":
        sheet_data = parse_txt(file_path)
    else:
        result = ImportResult()
        result.errors.append(ImportError(
            sheet="", row=0, field=None,
            message=f"不支持的文件格式「{file_ext}」，仅支持 .xlsx 和 .txt",
        ))
        result.error_count = 1
        return result

    if not sheet_data:
        result = ImportResult()
        result.errors.append(ImportError(
            sheet="", row=0, field=None,
            message="文件为空或无法解析",
        ))
        result.error_count = 1
        return result

    # 2. 按 Sheet 逐表检测模板并分组
    sheet_templates: dict[str, tuple[TemplateDef, list[dict[str, Any]]]] = {}
    unmatchable_sheets: list[str] = []

    for sheet_name, rows in sheet_data.items():
        if not rows:
            continue

        headers = [k for k in rows[0].keys() if not k.startswith("_")]
        tmpl = detect_template(headers)

        if tmpl:
            sheet_templates[sheet_name] = (tmpl, rows)
        else:
            unmatchable_sheets.append(sheet_name)

    if not sheet_templates:
        all_headers = {}
        for sname in unmatchable_sheets:
            if sheet_data[sname]:
                all_headers[sname] = [k for k in sheet_data[sname][0].keys() if not k.startswith("_")]

        result = ImportResult()
        result.errors.append(ImportError(
            sheet="", row=0, field=None,
            message=(
                f"无法识别文件模板。支持的模板：课程测试各题扣分情况、成绩汇总、成绩考勤情况。"
                f"各Sheet表头：{all_headers}"
            ),
        ))
        result.error_count = 1
        return result

    # 3. 合并结果（按模板分组，同一模板的 sheet 批量导入）
    merged = ImportResult()
    merged.detected_template = ", ".join(
        sorted({tmpl.name for tmpl, _ in sheet_templates.values()})
    )

    # 按 template_id 分组
    by_template: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for sname, (tmpl, rows) in sheet_templates.items():
        by_template.setdefault(tmpl.template_id, {})[sname] = rows

    for template_id, sheets in by_template.items():
        handler = IMPORT_HANDLERS.get(template_id)
        if not handler:
            merged.errors.append(ImportError(
                sheet="", row=0, field=None,
                message=f"模板 ID「{template_id}」的导入逻辑尚未实现",
            ))
            merged.error_count += 1
            continue

        # 取第一个 sheet 对应的模板定义
        first_tmpl = sheet_templates[next(iter(sheets))][0]
        partial = handler(session, sheets, course_id, create_by, first_tmpl)
        merged.success_count += partial.success_count
        merged.error_count += partial.error_count
        merged.errors.extend(partial.errors)
        merged.sheets_processed.extend(partial.sheets_processed)

    # 记录未匹配的 sheet（警告级别，不影响匹配成功的 sheet）
    if unmatchable_sheets:
        for sname in unmatchable_sheets:
            merged.errors.append(ImportError(
                sheet=sname, row=0, field=None,
                message=f"Sheet「{sname}」的数据格式未能匹配任何已知模板，已跳过",
            ))
            merged.error_count += 1

    return merged
