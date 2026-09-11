"""导出供“数据管理 → 数据库导入”直接上传的课程演示 SQLite 文件。"""
from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "app.db"
OUTPUT_DIR = ROOT / "docs" / "验收演示" / "导入数据"

COURSES = {
    1: "01-计算机网络-完整演示数据.sqlite",
    2: "02-操作系统-完整演示数据.sqlite",
    3: "03-数据结构-完整演示数据.sqlite",
    4: "04-软件工程-完整演示数据.sqlite",
    5: "05-概率论与数理统计-完整演示数据.sqlite",
}


def create_table(connection: sqlite3.Connection, name: str, columns: list[str]) -> None:
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    connection.execute(f'CREATE TABLE "{name}" ({quoted_columns})')


def export_course(source: sqlite3.Connection, course_id: int, output: Path) -> None:
    course = source.execute(
        "SELECT course_code, course_name, semester FROM course WHERE course_id = ?", (course_id,)
    ).fetchone()
    if course is None:
        raise RuntimeError(f"课程 {course_id} 不存在")
    course_code, course_name, semester = course
    target = sqlite3.connect(output)
    try:
        score_headers = ["编号", "课程号", "课程名称", "学期", "学号", "姓名", "成绩名称", "成绩"]
        attendance_headers = [
            "编号", "课程号", "课程名称", "学期", "学号", "姓名",
            *[f"考勤{i}" for i in range(1, 33)],
            "考勤总数", "到课数", "请假数", "早退数", "迟到数", "到课率",
        ]
        participation_headers = [
            "编号", "课程号", "课程名称", "学期", "学号", "姓名",
            *[f"课堂{i}" for i in range(1, 33)], "课堂总数", "课堂参与度",
        ]
        detail_headers = [
            "编号", "课程号", "课程名称", "学期", "测试名称", "学号", "姓名",
            "第1大题", "第 1 大题扣分的主要知识点",
            "第2大题", "第 2 大题扣分的主要知识点",
            "第3大题", "第 3 大题扣分的主要知识点",
            "第4大题", "第 4 大题扣分的主要知识点",
            "第5大题", "第 5 大题扣分的主要知识点", "总成绩",
        ]
        create_table(target, "单项成绩", score_headers)
        create_table(target, "成绩考勤情况", attendance_headers)
        create_table(target, "课堂参与情况", participation_headers)
        create_table(target, "课程测试各题扣分情况", detail_headers)

        score_rows = source.execute(
            """
            SELECT s.student_no, s.real_name, b.batch_name, r.score
            FROM score_record r
            JOIN student s ON s.student_id = r.student_id
            JOIN exam_batch b ON b.batch_id = r.batch_id
            WHERE r.course_id = ?
            ORDER BY s.student_no, b.exam_time, b.batch_id
            """,
            (course_id,),
        ).fetchall()
        target.executemany(
            'INSERT INTO "单项成绩" VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (index, course_code, course_name, semester, row[0], row[1], row[2], row[3])
                for index, row in enumerate(score_rows, start=1)
            ],
        )

        attendance_rows = source.execute(
            """
            SELECT s.student_no, s.real_name,
                   a.attendance_1, a.attendance_2, a.attendance_3, a.attendance_4,
                   a.attendance_5, a.attendance_6, a.attendance_7, a.attendance_8,
                   a.attendance_9, a.attendance_10, a.attendance_11, a.attendance_12,
                   a.attendance_13, a.attendance_14, a.attendance_15, a.attendance_16,
                   a.attendance_17, a.attendance_18, a.attendance_19, a.attendance_20,
                   a.attendance_21, a.attendance_22, a.attendance_23, a.attendance_24,
                   a.attendance_25, a.attendance_26, a.attendance_27, a.attendance_28,
                   a.attendance_29, a.attendance_30, a.attendance_31, a.attendance_32,
                   a.total_count, a.present_count, a.leave_count, a.early_leave_count,
                   a.late_count, a.attendance_rate
            FROM attendance_sheet a
            JOIN student s ON s.student_id = a.student_id
            JOIN exam_batch b ON b.batch_id = a.exam_batch_id
            WHERE b.course_id = ?
            ORDER BY s.student_no
            """,
            (course_id,),
        ).fetchall()
        target.executemany(
            'INSERT INTO "成绩考勤情况" VALUES (' + ",".join("?" for _ in attendance_headers) + ')',
            [
                (index, course_code, course_name, semester, *row)
                for index, row in enumerate(attendance_rows, start=1)
            ],
        )

        participation_rows = source.execute(
            """
            SELECT s.student_no, s.real_name,
                   p.participation_1, p.participation_2, p.participation_3, p.participation_4,
                   p.participation_5, p.participation_6, p.participation_7, p.participation_8,
                   p.participation_9, p.participation_10, p.participation_11, p.participation_12,
                   p.participation_13, p.participation_14, p.participation_15, p.participation_16,
                   p.participation_17, p.participation_18, p.participation_19, p.participation_20,
                   p.participation_21, p.participation_22, p.participation_23, p.participation_24,
                   p.participation_25, p.participation_26, p.participation_27, p.participation_28,
                   p.participation_29, p.participation_30, p.participation_31, p.participation_32,
                   p.total_count, p.participation_rate
            FROM participation_sheet p
            JOIN student s ON s.student_id = p.student_id
            JOIN exam_batch b ON b.batch_id = p.exam_batch_id
            WHERE b.course_id = ?
            ORDER BY s.student_no
            """,
            (course_id,),
        ).fetchall()
        target.executemany(
            'INSERT INTO "课堂参与情况" VALUES (' + ",".join("?" for _ in participation_headers) + ')',
            [
                (index, course_code, course_name, semester, *row)
                for index, row in enumerate(participation_rows, start=1)
            ],
        )

        points = [row[0] for row in source.execute(
            """
            SELECT kp.point_name FROM knowledge_point kp
            JOIN knowledge_module km ON km.module_id = kp.module_id
            WHERE km.course_id = ? ORDER BY kp.point_id LIMIT 5
            """,
            (course_id,),
        ).fetchall()]
        while len(points) < 5:
            points.append("课程核心知识点")
        midterm_rows = [row for row in score_rows if "期中" in str(row[2])]
        details = []
        for index, (student_no, student_name, _batch_name, score) in enumerate(midterm_rows, start=1):
            loss = round((100 - float(score)) / 5, 1)
            details.append((
                index, course_code, course_name, semester, "期中考试", student_no, student_name,
                loss, points[0], loss, points[1], loss, points[2], loss, points[3], loss, points[4], score,
            ))
        target.executemany(
            'INSERT INTO "课程测试各题扣分情况" VALUES (' + ",".join("?" for _ in detail_headers) + ')',
            details,
        )
        target.commit()
    finally:
        target.close()


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"未找到演示数据库：{SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SOURCE) as source:
        for course_id, filename in COURSES.items():
            output = OUTPUT_DIR / filename
            if output.exists():
                output.unlink()
            export_course(source, course_id, output)
            print(output)


if __name__ == "__main__":
    main()
