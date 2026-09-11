from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "验收演示" / "AI辅助教学评价系统演示数据与操作手册.docx"


def shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_text(paragraph, text, bold=False, color=None, size=None):
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if color:
        run.font.color.rgb = RGBColor(*color)
    if size:
        run.font.size = Pt(size)
    return run


def setup(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.62)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    for style_name, size in (("Title", 21), ("Heading 1", 15), ("Heading 2", 12)):
        style = doc.styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(7)


def add_heading(doc, text, level=1):
    return doc.add_heading(text, level=level)


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        add_text(p, item)


def add_numbered(doc, steps):
    for index, text in enumerate(steps, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.05)
        add_text(p, f"{index}. ", bold=True, color=(31, 78, 121))
        add_text(p, text)


def add_code(doc, command):
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    cell = table.cell(0, 0)
    shade(cell, "F2F4F7")
    set_cell_margins(cell, 100, 160, 100, 160)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(command)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    return table


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    header = table.rows[0]
    set_repeat_table_header(header)
    for i, title in enumerate(headers):
        cell = header.cells[i]
        shade(cell, "1F4E79")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_text(p, title, bold=True, color=(255, 255, 255), size=9.5)
        if widths:
            cell.width = Inches(widths[i])
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(values):
            if row_index % 2 == 1:
                shade(cells[i], "F7FAFC")
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cells[i])
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
            add_text(p, str(value), size=9.5)
            if widths:
                cells[i].width = Inches(widths[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def page_break(doc):
    doc.add_page_break()


def build() -> None:
    doc = Document()
    setup(doc)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(42)
    add_text(p, "AI辅助教学评价系统", bold=True, size=24)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(p, "验收演示数据与操作手册", bold=True, size=18, color=(31, 78, 121))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(22)
    add_text(p, "适用版本：数据管理模块 SQLite 导入演示数据集", size=11)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(p, "数据库：SQLite  |  前端：5173  |  后端：8000  |  AI服务：8001", size=10, color=(89, 89, 89))

    page_break(doc)
    add_heading(doc, "1. 演示前准备")
    add_numbered(doc, [
        "服务器先完成基础项目部署，并已初始化默认课程、教师和学生账号；导入文件只补充教学过程数据，不会创建学生账号。",
        "将“导入数据”目录中的五个 SQLite 文件上传或复制到可访问位置；不要替换服务器的 backend\\app.db。",
        "使用 teacher / 123456 登录，进入 数据采集 → 上传数据，数据类型选择“数据库导入”。",
        "先选择对应课程，再上传同名课程文件。每次只上传一个文件；导入完成后等待页面提示分析刷新完成，再切换下一门课程。",
    ])
    p = doc.add_paragraph()
    add_text(p, "完成标志：", bold=True)
    add_text(p, "上传结果显示“单项成绩、成绩考勤情况、课堂参与情况、课程测试各题扣分情况”，错误数为 0。")

    add_heading(doc, "2. 演示数据设计", level=1)
    add_table(doc, ["项目", "设计"], [
        ["课程", "计算机网络、操作系统、数据结构、软件工程、概率论与数理统计"],
        ["考核顺序", "平时作业 → 实验实践 → 期中考试 → 期末考试；期末固定最后"],
        ["覆盖量", "648 条选课关系、2,592 条成绩、648 条考勤、648 条课堂参与、3,240 条知识点掌握度；2024 级五个班各 20 人"],
        ["评分状态", "多数学生为良好或优秀；主演示学生为正向案例"],
        ["预警状态", "保留可用于演示预警与约谈的下滑风险案例；以页面实际刷新结果为准"],
    ], [1.3, 5.7])
    add_table(doc, ["上传课程", "上传文件", "预期导入量"], [
        ["计算机网络", "01-计算机网络-完整演示数据.sqlite", "1,183 条"],
        ["操作系统", "02-操作系统-完整演示数据.sqlite", "791 条"],
        ["数据结构", "03-数据结构-完整演示数据.sqlite", "889 条"],
        ["软件工程", "04-软件工程-完整演示数据.sqlite", "784 条"],
        ["概率论与数理统计", "05-概率论与数理统计-完整演示数据.sqlite", "889 条"],
    ], [1.4, 3.6, 2.0])
    page_break(doc)
    add_table(doc, ["账号", "用户名/密码", "演示用途"], [
        ["管理员", "admin / 123456", "用户、数据、日志、报告中心"],
        ["教师王建国", "teacher / 123456", "计算机网络、操作系统、学情分析、AI"],
        ["教师李明远", "teacher2 / 123456", "数据结构、软件工程、学情分析、AI"],
        ["教师陈晓芳", "teacher3 / 123456", "概率论与数理统计、学情分析、AI"],
        ["学生", "student / 123456", "赵伟；四门完整课程成绩和个人分析"],
        ["助教", "assistant / 123456", "数据采集与课程授权范围"],
    ], [1.0, 2.0, 4.0])

    add_heading(doc, "3. 启动项目")
    add_numbered(doc, [
        "启动后端。浏览器打开 http://127.0.0.1:8000/api/health，显示 status 为 ok 后继续。",
        "启动 AI 服务。浏览器打开 http://127.0.0.1:8001/health，确认服务可用；未配置第三方模型时，AI 生成功能应按页面提示处理。",
        "启动前端。浏览器打开 http://localhost:5173。",
    ])
    add_code(doc, "# 终端 1：在 backend 目录执行")
    add_code(doc, "..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000")
    add_code(doc, "# 终端 2：在 algorithm 目录执行")
    add_code(doc, ".venv\\Scripts\\python.exe -m uvicorn src.main:app --port 8001 --reload")
    add_code(doc, "# 终端 3：在 frontend 目录执行")
    add_code(doc, "npm run dev")

    page_break(doc)
    add_heading(doc, "4. 管理员演示", level=1)
    add_numbered(doc, [
        "使用 admin / 123456 登录。",
        "进入 系统管理 → 用户管理，搜索 2024001001。应看到赵伟的学生账号；账号可用于学生端登录。",
        "进入 数据管理，选择“成绩”筛选。查看五门课程的平时作业、实验实践、期中考试、期末考试记录；来源应为“提前注入”。",
        "进入 数据管理，切换考勤和课堂参与筛选。任一课程均应有对应记录，不应出现空白课程。",
        "进入 报告中心，选择班级或课程生成报告；预览后导出 PDF，确认下载文件包含与预览一致的图表。",
    ])

    page_break(doc)
    add_heading(doc, "5. 教师演示")
    add_numbered(doc, [
        "退出并使用 teacher / 123456 登录。",
        "进入 教师首页或课程管理，选择“计算机网络”。应看到完整的学生数量、成绩统计、考勤和参与数据。",
        "进入 学情分析 → 成绩趋势。选择班级与计算机网络；趋势按平时作业、实验实践、期中、期末排序，期末在最右侧。",
        "进入 学情分析 → 知识点掌握度。查看网络体系结构、数据链路层、传输层及知识点热力图；数据不应为空。",
        "进入 异常学情预警，点击“刷新预警”后查看系统根据当前成绩与过程数据生成的预警；打开详情说明原因。",
        "点击“去约谈”，完成预警学生的约谈记录。返回预警列表后确认该记录仍可追溯。",
        "进入 AI 学情分析，先选择班级、学期、课程和分析维度，再点击重新分析。先展示诊断过程，完成后展示分析结果；通过“历史分析与对话”可回到对应记录。",
    ])

    add_heading(doc, "6. 学生端演示", level=1)
    add_numbered(doc, [
        "退出并使用 student / 123456 登录。该账号对应赵伟，学号 2024001001。",
        "进入 我的学习。顶部课程卡应显示四门课程：计算机网络、操作系统、数据结构、概率论与数理统计。",
        "在“成绩变化趋势”右上角选择“计算机网络”。图表只显示该课程的四阶段成绩，最后一项为期末考试。",
        "切换到“操作系统”或“概率论与数理统计”，确认趋势数据随课程切换而变化，不与其他课程混在同一张图。",
        "进入 学习档案 → 成绩档案，选择同一课程。成绩记录、趋势图和首页趋势的阶段顺序应一致。",
        "进入 个人分析 → 学习评价，选择任一已有课程。课程成绩类型构成与学习态度数据来源应同时显示；无数据项不应参与总评。",
        "进入 个人分析 → 知识点掌握度。选择计算机网络，查看知识点热力图、最强知识点和需加强知识点。",
    ])

    page_break(doc)
    add_heading(doc, "7. AI教学与报告验收")
    add_numbered(doc, [
        "教师端进入 AI 智能辅助教学 → AI 出题。选择计算机网络的标准章节后生成题目，确认章节名统一且不重复。",
        "在生成题目列表中查看题型、难度、知识点和章节；接受题目后进入题库或任务管理查看。",
        "进入 AI 学情分析，选择“概览”深度执行一次分析。结果应以结构化内容展示，不应显示原始 JSON。",
        "点击“历史分析与对话”。列表中应显示班级、学期、班级名称、课程等区分信息；点击“进入这条对话”后，应切换到该条记录的结果与对话上下文。",
        "返回 报告中心，生成一份课程报告。先预览，再下载 PDF；图表、统计和文字内容应一致。",
    ])

    add_heading(doc, "8. 验收检查清单", level=1)
    add_table(doc, ["检查项", "通过标准"], [
        ["数据完整性", "五门课程均有四阶段成绩、考勤、参与和知识点数据"],
        ["趋势排序", "平时作业/实践在前，期中居中，期末固定最后"],
        ["学生端同步", "首页、成绩档案、学习评价使用同一门课程和同一顺序的数据"],
        ["评价口径", "学业水平来自课程成绩类型构成；学习态度来自考勤和课堂参与等明确来源"],
        ["预警合理性", "刷新后预警应有明确原因；非风险学生不被大量误报"],
        ["AI上下文", "分析完成即展示；历史记录可定位并进入原上下文"],
        ["报告一致性", "PDF 下载内容与页面预览包含一致的可视化图表"],
    ], [1.6, 5.4])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
