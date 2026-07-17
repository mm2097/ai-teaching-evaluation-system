"""Supplement demo data for AI-assisted teaching pages.

Run from backend:
    python -m app.seed_ai_teaching_data
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.core.database import engine, init_db
from app.models import (
    AiQuestion,
    AnswerTask,
    Course,
    CourseStudent,
    KnowledgeModule,
    KnowledgePoint,
    StudentAnswerRecord,
    TaskQuestion,
)
from app.services.question_answers import encode_correct_answer, judge_objective_answer

TYPE_MAP = {"single_choice": 1, "multi_choice": 2, "judge": 3, "fill_blank": 4, "short_answer": 5}

COURSE_POINTS = {
    "计算机网络": ["OSI 七层模型", "TCP/IP 协议族", "IP 地址与子网划分", "TCP 可靠传输", "UDP 协议", "HTTP 与 HTTPS", "DNS 解析", "网络安全"],
    "操作系统": ["进程状态", "进程调度", "进程同步", "分页存储", "虚拟内存", "页面置换", "文件系统", "磁盘调度"],
    "数据结构": ["顺序表", "链表", "栈与队列", "二叉树", "图遍历", "最短路径", "哈希表", "快速排序"],
    "软件工程": ["需求分析", "用例建模", "架构设计", "敏捷开发", "版本控制", "代码评审", "单元测试", "缺陷管理"],
    "概率论与数理统计": ["随机事件", "条件概率", "全概率公式", "离散型随机变量", "期望与方差", "常见分布", "参数估计", "假设检验"],
}

QUESTION_SETS: dict[str, list[dict[str, Any]]] = {
    "计算机网络": [
        {"type": "single_choice", "stem": "TCP 三次握手第二次握手的标志位组合是？", "point": "TCP 可靠传输", "answer": "C", "options": ["SYN", "ACK", "SYN+ACK", "FIN"]},
        {"type": "multi_choice", "stem": "以下哪些属于应用层协议？", "point": "HTTP 与 HTTPS", "answer": "AC", "answerList": ["A", "C"], "options": ["HTTP", "TCP", "DNS", "IP"]},
        {"type": "judge", "stem": "UDP 提供面向连接的可靠传输。", "point": "UDP 协议", "answer": "false"},
        {"type": "fill_blank", "stem": "HTTPS 默认端口号是 ____。", "point": "HTTP 与 HTTPS", "answer": "443", "answerList": ["443"]},
        {"type": "single_choice", "stem": "IPv4 地址长度是多少位？", "point": "IP 地址与子网划分", "answer": "B", "options": ["16", "32", "64", "128"]},
        {"type": "judge", "stem": "DNS 的核心作用是完成域名到 IP 地址的解析。", "point": "DNS 解析", "answer": "true"},
        {"type": "single_choice", "stem": "OSI 模型中负责端到端传输的是哪一层？", "point": "OSI 七层模型", "answer": "C", "options": ["网络层", "会话层", "传输层", "表示层"]},
        {"type": "short_answer", "stem": "简述 TCP 与 UDP 的主要区别。", "point": "TCP/IP 协议族", "answer": "TCP 面向连接且可靠，UDP 无连接且开销低。"},
    ],
    "操作系统": [
        {"type": "single_choice", "stem": "进程的三种基本状态不包括？", "point": "进程状态", "answer": "D", "options": ["就绪", "运行", "阻塞", "挂起"]},
        {"type": "multi_choice", "stem": "以下哪些属于进程同步问题？", "point": "进程同步", "answer": "AB", "answerList": ["A", "B"], "options": ["生产者消费者", "读者写者", "最短路径", "二分查找"]},
        {"type": "judge", "stem": "时间片轮转调度适合分时系统。", "point": "进程调度", "answer": "true"},
        {"type": "fill_blank", "stem": "分页存储管理中地址转换依赖 ____ 表。", "point": "分页存储", "answer": "页表", "answerList": ["页表", "页"]},
        {"type": "single_choice", "stem": "缺页中断发生时通常需要从哪里调入页面？", "point": "虚拟内存", "answer": "B", "options": ["寄存器", "外存", "高速缓存", "网卡"]},
        {"type": "judge", "stem": "LRU 页面置换算法需要利用最近访问历史。", "point": "页面置换", "answer": "true"},
        {"type": "single_choice", "stem": "SCAN 磁盘调度算法也常被称为？", "point": "磁盘调度", "answer": "B", "options": ["随机算法", "电梯算法", "堆算法", "银行家算法"]},
        {"type": "short_answer", "stem": "说明死锁产生的四个必要条件。", "point": "进程同步", "answer": "互斥、占有并等待、不可抢占、循环等待。"},
    ],
    "数据结构": [
        {"type": "single_choice", "stem": "栈的典型特性是？", "point": "栈与队列", "answer": "A", "options": ["后进先出", "先进先出", "随机访问", "按键排序"]},
        {"type": "multi_choice", "stem": "以下哪些结构可用于实现队列？", "point": "栈与队列", "answer": "AB", "answerList": ["A", "B"], "options": ["顺序存储", "链式存储", "递归函数", "哈希函数"]},
        {"type": "judge", "stem": "二叉搜索树中序遍历结果是有序序列。", "point": "二叉树", "answer": "true"},
        {"type": "fill_blank", "stem": "快速排序平均时间复杂度为 ____。", "point": "快速排序", "answer": "O(nlogn)", "answerList": ["O(nlogn)", "O(n log n)"]},
        {"type": "single_choice", "stem": "BFS 通常借助哪种辅助结构？", "point": "图遍历", "answer": "B", "options": ["栈", "队列", "堆", "集合"]},
        {"type": "judge", "stem": "链表适合频繁随机访问。", "point": "链表", "answer": "false"},
        {"type": "single_choice", "stem": "哈希冲突的常见处理方法是？", "point": "哈希表", "answer": "D", "options": ["二分查找", "归并排序", "深度优先", "链地址法"]},
        {"type": "short_answer", "stem": "简述顺序表和链表的主要区别。", "point": "顺序表", "answer": "顺序表连续存储、随机访问快；链表非连续存储、插删灵活。"},
    ],
    "软件工程": [
        {"type": "single_choice", "stem": "需求分析阶段最重要的产物通常是？", "point": "需求分析", "answer": "B", "options": ["源代码", "需求规格说明", "部署脚本", "测试报告"]},
        {"type": "multi_choice", "stem": "以下哪些属于敏捷实践？", "point": "敏捷开发", "answer": "ABC", "answerList": ["A", "B", "C"], "options": ["迭代开发", "每日站会", "持续集成", "瀑布式一次交付"]},
        {"type": "judge", "stem": "单元测试通常关注最小可测试代码单元。", "point": "单元测试", "answer": "true"},
        {"type": "fill_blank", "stem": "Git 中创建新分支常用命令是 git ____。", "point": "版本控制", "answer": "branch", "answerList": ["branch", "switch -c", "checkout -b"]},
        {"type": "single_choice", "stem": "用例图主要描述系统与谁之间的交互？", "point": "用例建模", "answer": "A", "options": ["参与者", "数据库", "编译器", "线程"]},
        {"type": "judge", "stem": "代码评审只关注代码格式，不关注设计问题。", "point": "代码评审", "answer": "false"},
        {"type": "single_choice", "stem": "集成测试的重点是？", "point": "架构设计", "answer": "C", "options": ["单个函数", "变量命名", "模块协作", "图标颜色"]},
        {"type": "short_answer", "stem": "简述缺陷管理流程的关键环节。", "point": "缺陷管理", "answer": "发现、记录、分派、修复、验证、关闭。"},
    ],
    "概率论与数理统计": [
        {"type": "single_choice", "stem": "两个独立事件 A、B 满足 P(AB)=？", "point": "随机事件", "answer": "C", "options": ["P(A)+P(B)", "P(A)-P(B)", "P(A)P(B)", "P(A)/P(B)"]},
        {"type": "multi_choice", "stem": "以下哪些是离散型分布？", "point": "常见分布", "answer": "AB", "answerList": ["A", "B"], "options": ["二项分布", "泊松分布", "正态分布", "连续均匀分布"]},
        {"type": "judge", "stem": "方差一定不会小于 0。", "point": "期望与方差", "answer": "true"},
        {"type": "fill_blank", "stem": "条件概率公式 P(A|B)=P(AB)/____。", "point": "条件概率", "answer": "P(B)", "answerList": ["P(B)"]},
        {"type": "single_choice", "stem": "样本均值通常用于估计总体的哪个参数？", "point": "参数估计", "answer": "A", "options": ["均值", "中位数", "众数", "极差"]},
        {"type": "judge", "stem": "显著性水平越小，拒绝原假设的标准越严格。", "point": "假设检验", "answer": "true"},
        {"type": "single_choice", "stem": "全概率公式适用于哪类事件组？", "point": "全概率公式", "answer": "D", "options": ["任意两个事件", "互斥但不完备", "独立但不互斥", "完备事件组"]},
        {"type": "short_answer", "stem": "说明期望和方差分别刻画随机变量的什么特征。", "point": "期望与方差", "answer": "期望刻画平均水平，方差刻画围绕均值的离散程度。"},
    ],
}


def get_or_create_point(session: Session, course_id: int, point_name: str, sort_num: int) -> KnowledgePoint:
    module = session.exec(select(KnowledgeModule).where(KnowledgeModule.course_id == course_id, KnowledgeModule.module_name == "AI 辅助教学知识点")).first()
    if not module:
        module = KnowledgeModule(course_id=course_id, module_name="AI 辅助教学知识点", sort_num=99)
        session.add(module)
        session.commit()
        session.refresh(module)
    point = session.exec(select(KnowledgePoint).where(KnowledgePoint.module_id == module.module_id, KnowledgePoint.point_name == point_name)).first()
    if not point:
        point = KnowledgePoint(module_id=module.module_id, point_name=point_name, sort_num=sort_num)
        session.add(point)
        session.commit()
        session.refresh(point)
    return point


def ensure_question(session: Session, course: Course, row: dict[str, Any], sort_num: int) -> AiQuestion:
    existing = session.exec(select(AiQuestion).where(AiQuestion.course_id == course.course_id, AiQuestion.content == row["stem"])).first()
    if existing:
        return existing
    point = get_or_create_point(session, course.course_id, row["point"], sort_num)
    q_type = TYPE_MAP[row["type"]]
    options = row.get("options")
    question = AiQuestion(
        course_id=course.course_id,
        point_id=point.point_id,
        type=q_type,
        content=row["stem"],
        options=json.dumps([{"key": chr(65 + i), "text": text} for i, text in enumerate(options)], ensure_ascii=False) if options else None,
        correct_answer=encode_correct_answer(q_type, row["answer"], row.get("answerList")),
        analysis=row.get("analysis") or "用于课程题库演示与组卷参考。",
        difficulty="hard" if row["type"] == "short_answer" else "medium",
        source="manual",
        create_by=course.teacher_id + 1,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    return question


def ensure_task(session: Session, course: Course, questions: list[AiQuestion]) -> AnswerTask:
    task_name = f"{course.course_name} 单元巩固练习"
    task = session.exec(select(AnswerTask).where(AnswerTask.course_id == course.course_id, AnswerTask.task_name == task_name)).first()
    if not task:
        now = datetime.now()
        task = AnswerTask(
            course_id=course.course_id,
            task_name=task_name,
            publish_time=now - timedelta(days=1),
            deadline=now + timedelta(days=14),
            status=1,
            max_attempts=2,
            allow_review=1,
            create_by=course.teacher_id + 1,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
    linked = {rel.question_id for rel in session.exec(select(TaskQuestion).where(TaskQuestion.task_id == task.task_id)).all()}
    for index, question in enumerate(questions[:6], start=1):
        if question.question_id not in linked:
            session.add(TaskQuestion(task_id=task.task_id, question_id=question.question_id, sort_num=index))
    session.commit()
    return task


def wrong_answer(question: AiQuestion) -> str:
    if question.type == 1:
        return "A" if question.correct_answer.upper() != "A" else "B"
    if question.type == 2:
        return "A"
    if question.type == 3:
        return "false" if question.correct_answer == "true" else "true"
    if question.type == 4:
        return "未掌握"
    return "回答不完整"


def ensure_answer_records(session: Session, task: AnswerTask, questions: list[AiQuestion]) -> int:
    student_ids = session.exec(select(CourseStudent.student_id).where(CourseStudent.course_id == task.course_id, CourseStudent.status == 1).limit(8)).all()
    added = 0
    for s_index, student_id in enumerate(student_ids):
        for q_index, question in enumerate(questions[:6]):
            exists = session.exec(select(StudentAnswerRecord).where(StudentAnswerRecord.task_id == task.task_id, StudentAnswerRecord.student_id == student_id, StudentAnswerRecord.question_id == question.question_id)).first()
            if exists:
                continue
            correct = (s_index + q_index) % 4 != 0
            user_answer = question.correct_answer if correct else wrong_answer(question)
            is_correct = judge_objective_answer(question.type, question.correct_answer, user_answer)
            score = round(100 / 6, 1) if is_correct else 0.0
            session.add(StudentAnswerRecord(task_id=task.task_id, question_id=question.question_id, student_id=student_id, user_answer=user_answer, score=score, is_correct=1 if is_correct else 0, ai_score=score if question.type == 5 else None, judge_reason="演示数据自动评分" if question.type == 5 else None))
            added += 1
    session.commit()
    return added


def seed_ai_teaching_data() -> None:
    init_db()
    with Session(engine) as session:
        for course_name, points in COURSE_POINTS.items():
            course = session.exec(select(Course).where(Course.course_name == course_name)).first()
            if not course:
                continue
            for index, point in enumerate(points, start=1):
                get_or_create_point(session, course.course_id, point, index)
            questions = [ensure_question(session, course, row, index) for index, row in enumerate(QUESTION_SETS[course_name], start=1)]
            task = ensure_task(session, course, questions)
            added_answers = ensure_answer_records(session, task, questions)
            print(f"{course.course_id} {course.course_name}: questions={len(questions)} task={task.task_id} new_answers={added_answers}")


if __name__ == "__main__":
    seed_ai_teaching_data()