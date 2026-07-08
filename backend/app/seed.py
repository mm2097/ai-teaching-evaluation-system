"""Seed 脚本:灌入统一的演示数据。

用法:
    python -m app.seed              # 灌入数据(表不存在会自动建)
    python -m app.seed --reset      # 删库重建后再灌入(推荐,回到干净起点)

新增表后,在 seed() 函数里照着示例加插入语句即可。
"""
from __future__ import annotations

import argparse
from datetime import date, datetime

from sqlmodel import Session, SQLModel, select

from app.core.database import engine, init_db
from app.models import (
    SysUser, SysRole, Teacher, Student, ClassInfo, Course, CourseStudent,
    KnowledgeModule, KnowledgePoint,
    AttendanceRecord, InteractionRecord,
    ExamBatch, ScoreRecord,
    AiQuestion, AnswerTask, TaskQuestion, StudentAnswerRecord,
    EvalDimension, EvalIndex, StudentEvaluationResult, EvalDimensionScore,
    KnowledgeMastery, StudyWarning, StudentProfile,
    SysOperationLog,
)


def reset() -> None:
    """删除所有表后重建,回到干净起点。"""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("[seed] 数据库已重建")


def seed() -> None:
    """灌入演示数据。"""
    init_db()  # 表不存在时自动创建
    with Session(engine) as session:
        # 已有数据则跳过，避免重复灌入
        existing = session.exec(select(SysRole)).first()
        if existing:
            print("[seed] 数据已存在,跳过")
            return

        # ====== 1. 角色 ======
        roles = [
            SysRole(role_name="系统管理员", role_code="admin", description="管理系统所有功能"),
            SysRole(role_name="任课教师", role_code="teacher", description="管理课程、查看学情分析"),
            SysRole(role_name="学生", role_code="student", description="查看个人成绩、答题、评价"),
        ]
        session.add_all(roles)
        session.commit()
        print(f"  已创建 {len(roles)} 个角色")

        # ====== 2. 系统用户 ======
        users = [
            SysUser(username="admin", password="123456", real_name="张管理", role_id=1, status=1),
            SysUser(username="teacher", password="123456", real_name="王教授", role_id=2, status=1),
            SysUser(username="teacher2", password="123456", real_name="李副教授", role_id=2, status=1),
            SysUser(username="student", password="123456", real_name="陈同学", role_id=3, status=1),
            SysUser(username="student2", password="123456", real_name="赵同学", role_id=3, status=1),
        ]
        session.add_all(users)
        session.commit()
        print(f"  已创建 {len(users)} 个用户")

        # ====== 3. 教师 ======
        teachers = [
            Teacher(teacher_no="T001", real_name="王教授", title="教授",
                    user_id=2, college="计算机学院", phone="13800000001", email="wang@edu.cn"),
            Teacher(teacher_no="T002", real_name="李副教授", title="副教授",
                    user_id=3, college="计算机学院", phone="13800000002", email="li@edu.cn"),
        ]
        session.add_all(teachers)
        session.commit()
        print(f"  已创建 {len(teachers)} 位教师")

        # ====== 4. 班级 ======
        classes = [
            ClassInfo(class_name="计科2201班", college="计算机学院", enroll_year=2022),
            ClassInfo(class_name="计科2202班", college="计算机学院", enroll_year=2022),
        ]
        session.add_all(classes)
        session.commit()
        print(f"  已创建 {len(classes)} 个班级")

        # ====== 5. 学生 ======
        students = [
            Student(student_no="S2022001", real_name="陈同学", gender=1,
                    class_id=1, user_id=4, phone="13900000001"),
            Student(student_no="S2022002", real_name="赵同学", gender=0,
                    class_id=1, user_id=5, phone="13900000002"),
        ]
        session.add_all(students)
        session.commit()
        print(f"  已创建 {len(students)} 名学生")

        # ====== 6. 课程 ======
        courses = [
            Course(course_code="CS3001", course_name="计算机网络", teacher_id=1,
                   semester="2025-2026-1", college="计算机学院", credit=3.0, status=1),
            Course(course_code="CS3002", course_name="操作系统", teacher_id=1,
                   semester="2025-2026-1", college="计算机学院", credit=4.0, status=1),
            Course(course_code="CS3003", course_name="数据结构", teacher_id=2,
                   semester="2025-2026-1", college="计算机学院", credit=3.5, status=1),
        ]
        session.add_all(courses)
        session.commit()
        print(f"  已创建 {len(courses)} 门课程")

        # ====== 7. 课程选修 ======
        course_students = [
            CourseStudent(course_id=1, student_id=1),
            CourseStudent(course_id=1, student_id=2),
            CourseStudent(course_id=2, student_id=1),
        ]
        session.add_all(course_students)
        session.commit()
        print(f"  已创建 {len(course_students)} 条选修关系")

        # ====== 8. 知识模块 & 知识点 ======
        modules = [
            KnowledgeModule(course_id=1, module_name="网络基础", description="网络体系结构、协议基本概念", sort_num=1),
            KnowledgeModule(course_id=1, module_name="传输层", description="TCP/UDP 协议", sort_num=2),
        ]
        session.add_all(modules)
        session.commit()

        points = [
            KnowledgePoint(module_id=1, point_name="OSI 七层模型", sort_num=1),
            KnowledgePoint(module_id=1, point_name="TCP/IP 协议栈", sort_num=2),
            KnowledgePoint(module_id=2, point_name="TCP 三次握手", sort_num=1),
            KnowledgePoint(module_id=2, point_name="UDP 协议特点", sort_num=2),
        ]
        session.add_all(points)
        session.commit()
        print(f"  已创建 {len(modules)} 个知识模块、{len(points)} 个知识点")

        # ====== 9. 考核批次 ======
        batches = [
            ExamBatch(course_id=1, batch_name="平时作业1", batch_type=1, batch_weight=20,
                      exam_time=datetime(2026, 3, 15, 10, 0), full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期中考试", batch_type=3, batch_weight=30,
                      exam_time=datetime(2026, 4, 20, 14, 0), full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期末考试", batch_type=4, batch_weight=50,
                      exam_time=datetime(2026, 6, 25, 9, 0), full_score=100, create_by=2),
            ExamBatch(course_id=2, batch_name="平时作业1", batch_type=1, batch_weight=30,
                      exam_time=datetime(2026, 3, 10, 10, 0), full_score=100, create_by=2),
        ]
        session.add_all(batches)
        session.commit()
        print(f"  已创建 {len(batches)} 个考核批次")

        # ====== 10. 成绩记录 ======
        scores = [
            ScoreRecord(course_id=1, student_id=1, batch_id=1, score=85, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=1, batch_id=2, score=72, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=1, batch_id=3, score=78, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=2, batch_id=1, score=90, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=2, batch_id=2, score=65, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=1, batch_id=4, score=55, is_pass=0, create_by=2),
        ]
        session.add_all(scores)
        session.commit()
        print(f"  已创建 {len(scores)} 条成绩记录")

        # ====== 11. 考勤记录 ======
        attendances = [
            AttendanceRecord(course_id=1, student_id=1, attendance_date=date(2026, 3, 3),
                             status=0, remark="正常", create_by=2),
            AttendanceRecord(course_id=1, student_id=1, attendance_date=date(2026, 3, 10),
                             status=1, remark="迟到5分钟", create_by=2),
            AttendanceRecord(course_id=1, student_id=2, attendance_date=date(2026, 3, 3),
                             status=0, create_by=2),
            AttendanceRecord(course_id=1, student_id=2, attendance_date=date(2026, 3, 10),
                             status=3, remark="未到", create_by=2),
        ]
        session.add_all(attendances)
        session.commit()
        print(f"  已创建 {len(attendances)} 条考勤记录")

        # ====== 12. 课堂互动 ======
        interactions = [
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 5),
                              type=1, score=8.5, remark="回答积极", create_by=2),
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 12),
                              type=3, score=9.0, create_by=2),
            InteractionRecord(course_id=1, student_id=2, interaction_date=date(2026, 3, 5),
                              type=2, score=7.0, create_by=2),
        ]
        session.add_all(interactions)
        session.commit()
        print(f"  已创建 {len(interactions)} 条互动记录")

        # ====== 13. AI 题目 ======
        questions = [
            AiQuestion(course_id=1, point_id=1, type=1,
                       content="OSI 参考模型共分为几层？",
                       options='["A. 5层","B. 6层","C. 7层","D. 8层"]',
                       correct_answer="C",
                       analysis="OSI 参考模型分为物理层、数据链路层、网络层、传输层、会话层、表示层、应用层共7层。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=1, type=2,
                       content="以下哪些属于 TCP/IP 协议栈的应用层协议？（多选）",
                       options='["A. HTTP","B. TCP","C. FTP","D. IP"]',
                       correct_answer='["A","C"]',
                       analysis="HTTP 和 FTP 属于应用层协议，TCP 属于传输层，IP 属于网络层。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=3, type=3,
                       content="TCP 三次握手过程中，第一次握手由客户端发送 SYN 包。",
                       options='["正确","错误"]',
                       correct_answer="正确",
                       create_by=2),
        ]
        session.add_all(questions)
        session.commit()
        print(f"  已创建 {len(questions)} 道 AI 题目")

        # ====== 14. 答题任务 ======
        tasks = [
            AnswerTask(course_id=1, task_name="计算机网络单元测验1",
                       deadline=datetime(2026, 4, 30, 23, 59), status=1, create_by=2),
        ]
        session.add_all(tasks)
        session.commit()

        task_questions = [
            TaskQuestion(task_id=1, question_id=1, sort_num=1),
            TaskQuestion(task_id=1, question_id=2, sort_num=2),
            TaskQuestion(task_id=1, question_id=3, sort_num=3),
        ]
        session.add_all(task_questions)
        session.commit()
        print(f"  已创建 {len(tasks)} 个答题任务、{len(task_questions)} 条题目关联")

        # ====== 15. 学生答题记录 ======
        answers = [
            StudentAnswerRecord(task_id=1, question_id=1, student_id=1,
                                user_answer="C", score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=2, student_id=1,
                                user_answer='["A","C"]', score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=3, student_id=1,
                                user_answer="正确", score=5, is_correct=1),
        ]
        session.add_all(answers)
        session.commit()
        print(f"  已创建 {len(answers)} 条答题记录")

        # ====== 16. 评价维度 & 指标 ======
        dimensions = [
            EvalDimension(course_id=1, dimension_name="学业成绩", description="考核成绩综合评价", sort_num=1),
            EvalDimension(course_id=1, dimension_name="学习态度", description="考勤和课堂参与度", sort_num=2),
        ]
        session.add_all(dimensions)
        session.commit()

        indexes = [
            EvalIndex(dimension_id=1, index_name="期末成绩", weight=40,
                      score_rule='{"type":"direct","source":"score_record","batch_type":4}'),
            EvalIndex(dimension_id=1, index_name="平时成绩", weight=30,
                      score_rule='{"type":"direct","source":"score_record","batch_type":1}'),
            EvalIndex(dimension_id=1, index_name="期中成绩", weight=30,
                      score_rule='{"type":"direct","source":"score_record","batch_type":3}'),
            EvalIndex(dimension_id=2, index_name="出勤率", weight=50,
                      score_rule='{"type":"attendance","full_score":100}'),
            EvalIndex(dimension_id=2, index_name="课堂参与", weight=50,
                      score_rule='{"type":"interaction","full_score":100}'),
        ]
        session.add_all(indexes)
        session.commit()
        print(f"  已创建 {len(dimensions)} 个评价维度、{len(indexes)} 个指标")

        # ====== 17. 评价结果 ======
        eval_results = [
            StudentEvaluationResult(course_id=1, student_id=1, total_score=78.5,
                                    eval_level="中等"),
            StudentEvaluationResult(course_id=1, student_id=2, total_score=82.0,
                                    eval_level="良好"),
        ]
        session.add_all(eval_results)
        session.commit()

        dimension_scores = [
            EvalDimensionScore(eval_id=1, dimension_id=1, dimension_score=75.0),
            EvalDimensionScore(eval_id=1, dimension_id=2, dimension_score=82.0),
            EvalDimensionScore(eval_id=2, dimension_id=1, dimension_score=80.0),
            EvalDimensionScore(eval_id=2, dimension_id=2, dimension_score=84.0),
        ]
        session.add_all(dimension_scores)
        session.commit()
        print(f"  已创建 {len(eval_results)} 条评价结果、{len(dimension_scores)} 条维度得分")

        # ====== 18. 知识点掌握度 ======
        masteries = [
            KnowledgeMastery(course_id=1, student_id=1, point_id=1,
                             mastery_score=85, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=2,
                             mastery_score=70, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=1, point_id=3,
                             mastery_score=60, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=1, point_id=4,
                             mastery_score=45, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=2, point_id=1,
                             mastery_score=92, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=2, point_id=3,
                             mastery_score=55, mastery_level=2),
        ]
        session.add_all(masteries)
        session.commit()
        print(f"  已创建 {len(masteries)} 条掌握度记录")

        # ====== 19. 学情预警 ======
        warnings = [
            StudyWarning(course_id=2, student_id=1,
                         warning_type="成绩下滑", warning_level=2,
                         warning_reason="期中成绩较平时下降明显，需关注",
                         handle_status=0),
            StudyWarning(course_id=1, student_id=2,
                         warning_type="缺勤超标", warning_level=1,
                         warning_reason="本学期缺勤1次",
                         handle_status=0),
        ]
        session.add_all(warnings)
        session.commit()
        print(f"  已创建 {len(warnings)} 条预警记录")

        # ====== 20. 学情画像 ======
        profiles = [
            StudentProfile(course_id=1, student_id=1,
                           academic_score=72.0, attitude_score=82.0, progress_score=65.0,
                           total_profile_score=73.0,
                           study_tags="基础较好,答题积极",
                           good_modules="网络基础",
                           weak_modules="UDP协议"),
            StudentProfile(course_id=1, student_id=2,
                           academic_score=78.0, attitude_score=75.0, progress_score=80.0,
                           total_profile_score=77.5,
                           study_tags="进步明显",
                           good_modules="网络基础",
                           weak_modules="TCP握手"),
        ]
        session.add_all(profiles)
        session.commit()
        print(f"  已创建 {len(profiles)} 份学情画像")

        # ====== 21. 操作日志 ======
        logs = [
            SysOperationLog(user_id=1, module="用户管理", operation="新增",
                            content="创建教师账号 teacher", ip_address="127.0.0.1"),
            SysOperationLog(user_id=1, module="数据管理", operation="导入",
                            content="导入计算机网络课程成绩数据", ip_address="127.0.0.1"),
            SysOperationLog(user_id=2, module="课程管理", operation="编辑",
                            content="修改计算机网络课程信息", ip_address="127.0.0.1"),
        ]
        session.add_all(logs)
        session.commit()
        print(f"  已创建 {len(logs)} 条操作日志")

    print("[seed] 演示数据已灌入")


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入演示数据")
    parser.add_argument("--reset", action="store_true", help="删库重建后再灌入")
    args = parser.parse_args()

    if args.reset:
        reset()
    seed()


if __name__ == "__main__":
    main()
