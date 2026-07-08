"""Seed 脚本：灌入丰富的差异化演示数据。

用法:
    python -m app.seed              # 灌入数据（表不存在会自动建）
    python -m app.seed --reset      # 删库重建后再灌入（推荐）
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
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("[seed] 数据库已重建")


def seed() -> None:
    init_db()
    with Session(engine) as session:
        existing = session.exec(select(SysRole)).first()
        if existing:
            print("[seed] 数据已存在，跳过")
            return

        # ========== 1. 角色 ==========
        roles = [
            SysRole(role_name="系统管理员", role_code="admin", description="管理系统所有功能"),
            SysRole(role_name="任课教师", role_code="teacher", description="管理课程、查看学情分析"),
            SysRole(role_name="学生", role_code="student", description="查看个人成绩、答题、评价"),
        ]
        session.add_all(roles)
        session.commit()
        print(f"  角色: {len(roles)} 条")

        # ========== 2. 用户（10人） ==========
        users = [
            SysUser(username="admin", password="123456", real_name="张管理", role_id=1, status=1),
            SysUser(username="teacher", password="123456", real_name="王建国", role_id=2, status=1),
            SysUser(username="teacher2", password="123456", real_name="李明远", role_id=2, status=1),
            SysUser(username="teacher3", password="123456", real_name="陈晓芳", role_id=2, status=1),
            SysUser(username="student", password="123456", real_name="赵伟", role_id=3, status=1),
            SysUser(username="stu02", password="123456", real_name="钱丽华", role_id=3, status=1),
            SysUser(username="stu03", password="123456", real_name="孙浩然", role_id=3, status=1),
            SysUser(username="stu04", password="123456", real_name="周敏", role_id=3, status=1),
            SysUser(username="stu05", password="123456", real_name="吴天宇", role_id=3, status=1),
            SysUser(username="stu06", password="123456", real_name="郑雨涵", role_id=3, status=1),
            SysUser(username="stu07", password="123456", real_name="冯文博", role_id=3, status=1),
            SysUser(username="stu08", password="123456", real_name="郑小红", role_id=3, status=1),
            SysUser(username="stu09", password="123456", real_name="王志强", role_id=3, status=1),
            SysUser(username="stu10", password="123456", real_name="李思琪", role_id=3, status=1),
        ]
        session.add_all(users)
        session.commit()
        print(f"  用户: {len(users)} 条")

        # ========== 3. 教师（4人，不同职称） ==========
        teachers = [
            Teacher(teacher_no="T001", real_name="王建国", title="教授",
                    user_id=2, college="计算机学院", phone="13800000001", email="wjg@edu.cn"),
            Teacher(teacher_no="T002", real_name="李明远", title="副教授",
                    user_id=3, college="计算机学院", phone="13800000002", email="lmy@edu.cn"),
            Teacher(teacher_no="T003", real_name="陈晓芳", title="讲师",
                    user_id=4, college="数学与统计学院", phone="13800000003", email="cxf@edu.cn"),
        ]
        session.add_all(teachers)
        session.commit()
        print(f"  教师: {len(teachers)} 条")

        # ========== 4. 班级（5个） ==========
        classes = [
            ClassInfo(class_name="计科2401班", college="计算机学院", enroll_year=2024),
            ClassInfo(class_name="计科2402班", college="计算机学院", enroll_year=2024),
            ClassInfo(class_name="软工2401班", college="计算机学院", enroll_year=2024),
            ClassInfo(class_name="计科2301班", college="计算机学院", enroll_year=2023),
            ClassInfo(class_name="数统2401班", college="数学与统计学院", enroll_year=2024),
        ]
        session.add_all(classes)
        session.commit()
        print(f"  班级: {len(classes)} 条")

        # ========== 5. 学生（10人，分散在不同班级、不同性别） ==========
        students = [
            Student(student_no="2024001001", real_name="赵伟", gender=1,
                    class_id=1, user_id=5, phone="13900000001", email="zw@stu.edu.cn"),
            Student(student_no="2024001002", real_name="钱丽华", gender=0,
                    class_id=1, user_id=6, phone="13900000002", email="qlh@stu.edu.cn"),
            Student(student_no="2024001003", real_name="孙浩然", gender=1,
                    class_id=1, user_id=7, phone="13900000003", email="shr@stu.edu.cn"),
            Student(student_no="2024001004", real_name="周敏", gender=0,
                    class_id=2, user_id=8, phone="13900000004", email="zm@stu.edu.cn"),
            Student(student_no="2024001005", real_name="吴天宇", gender=1,
                    class_id=2, user_id=9, phone="13900000005", email="wty@stu.edu.cn"),
            Student(student_no="2024001006", real_name="郑雨涵", gender=0,
                    class_id=3, user_id=10, phone="13900000006", email="zyh@stu.edu.cn"),
            Student(student_no="2024001007", real_name="冯文博", gender=1,
                    class_id=3, user_id=11, phone="13900000007", email="fwb@stu.edu.cn"),
            Student(student_no="2024001008", real_name="郑小红", gender=0,
                    class_id=4, user_id=12, phone="13900000008", email="zxh@stu.edu.cn"),
            Student(student_no="2024001009", real_name="王志强", gender=1,
                    class_id=4, user_id=13, phone="13900000009", email="wzq@stu.edu.cn"),
            Student(student_no="2024001010", real_name="李思琪", gender=0,
                    class_id=5, user_id=14, phone="13900000010", email="lsq@stu.edu.cn"),
        ]
        session.add_all(students)
        session.commit()
        print(f"  学生: {len(students)} 条")

        # ========== 6. 课程（5门，跨两个学院） ==========
        courses = [
            Course(course_code="CS3001", course_name="计算机网络", teacher_id=1,
                   semester="2025-2026-1", college="计算机学院", credit=3.0, status=1),
            Course(course_code="CS3002", course_name="操作系统", teacher_id=1,
                   semester="2025-2026-1", college="计算机学院", credit=4.0, status=1),
            Course(course_code="CS3003", course_name="数据结构", teacher_id=2,
                   semester="2025-2026-1", college="计算机学院", credit=3.5, status=1),
            Course(course_code="SE3001", course_name="软件工程", teacher_id=2,
                   semester="2025-2026-1", college="计算机学院", credit=3.0, status=1),
            Course(course_code="MA3001", course_name="概率论与数理统计", teacher_id=3,
                   semester="2025-2026-1", college="数学与统计学院", credit=4.0, status=1),
        ]
        session.add_all(courses)
        session.commit()
        print(f"  课程: {len(courses)} 条")

        # ========== 7. 选修关系（差异化：不同学生选不同课） ==========
        course_students = [
            # 计算机网络：6人选
            CourseStudent(course_id=1, student_id=1),
            CourseStudent(course_id=1, student_id=2),
            CourseStudent(course_id=1, student_id=3),
            CourseStudent(course_id=1, student_id=4),
            CourseStudent(course_id=1, student_id=5),
            CourseStudent(course_id=1, student_id=8),
            # 操作系统：4人选
            CourseStudent(course_id=2, student_id=1),
            CourseStudent(course_id=2, student_id=3),
            CourseStudent(course_id=2, student_id=4),
            CourseStudent(course_id=2, student_id=6),
            # 数据结构：5人选
            CourseStudent(course_id=3, student_id=2),
            CourseStudent(course_id=3, student_id=5),
            CourseStudent(course_id=3, student_id=6),
            CourseStudent(course_id=3, student_id=7),
            CourseStudent(course_id=3, student_id=9),
            # 软件工程：3人选
            CourseStudent(course_id=4, student_id=7),
            CourseStudent(course_id=4, student_id=8),
            CourseStudent(course_id=4, student_id=10),
            # 概率论：4人选
            CourseStudent(course_id=5, student_id=1),
            CourseStudent(course_id=5, student_id=2),
            CourseStudent(course_id=5, student_id=9),
            CourseStudent(course_id=5, student_id=10),
        ]
        session.add_all(course_students)
        session.commit()
        print(f"  选修关系: {len(course_students)} 条")

        # ========== 8. 知识模块 & 知识点 ==========
        modules = [
            KnowledgeModule(course_id=1, module_name="网络体系结构", description="OSI 与 TCP/IP 模型", sort_num=1),
            KnowledgeModule(course_id=1, module_name="数据链路层", description="以太网协议与 MAC", sort_num=2),
            KnowledgeModule(course_id=1, module_name="传输层", description="TCP/UDP 协议", sort_num=3),
            KnowledgeModule(course_id=2, module_name="进程管理", description="进程与线程、调度算法", sort_num=1),
            KnowledgeModule(course_id=2, module_name="内存管理", description="虚拟内存与页面置换", sort_num=2),
            KnowledgeModule(course_id=3, module_name="线性结构", description="数组、链表、栈、队列", sort_num=1),
            KnowledgeModule(course_id=3, module_name="树与图", description="二叉树、B树、图遍历", sort_num=2),
            KnowledgeModule(course_id=3, module_name="排序算法", description="常见排序算法与复杂度", sort_num=3),
        ]
        session.add_all(modules)
        session.commit()

        points = [
            KnowledgePoint(module_id=1, point_name="OSI 七层模型", sort_num=1),
            KnowledgePoint(module_id=1, point_name="TCP/IP 四层模型", sort_num=2),
            KnowledgePoint(module_id=2, point_name="以太网帧格式", sort_num=1),
            KnowledgePoint(module_id=2, point_name="ARP 协议", sort_num=2),
            KnowledgePoint(module_id=3, point_name="TCP 三次握手", sort_num=1),
            KnowledgePoint(module_id=3, point_name="TCP 四次挥手", sort_num=2),
            KnowledgePoint(module_id=3, point_name="UDP 协议特点", sort_num=3),
            KnowledgePoint(module_id=4, point_name="进程状态转换", sort_num=1),
            KnowledgePoint(module_id=4, point_name="死锁检测与预防", sort_num=2),
            KnowledgePoint(module_id=5, point_name="页面置换算法", sort_num=1),
            KnowledgePoint(module_id=6, point_name="链表操作", sort_num=1),
            KnowledgePoint(module_id=6, point_name="栈与队列", sort_num=2),
            KnowledgePoint(module_id=7, point_name="二叉树遍历", sort_num=1),
            KnowledgePoint(module_id=7, point_name="图的遍历", sort_num=2),
            KnowledgePoint(module_id=8, point_name="快速排序", sort_num=1),
            KnowledgePoint(module_id=8, point_name="归并排序", sort_num=2),
        ]
        session.add_all(points)
        session.commit()
        print(f"  知识模块: {len(modules)} 个，知识点: {len(points)} 个")

        # ========== 9. 考核批次（每门课 3~4 次，权重不同） ==========
        batches = [
            # 计算机网络
            ExamBatch(course_id=1, batch_name="平时作业", batch_type=1, batch_weight=20,
                      exam_time=datetime(2026, 3, 20, 10, 0), full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="实验报告", batch_type=2, batch_weight=15,
                      exam_time=datetime(2026, 4, 10, 10, 0), full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期中考试", batch_type=3, batch_weight=25,
                      exam_time=datetime(2026, 4, 25, 14, 0), full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期末考试", batch_type=4, batch_weight=40,
                      exam_time=datetime(2026, 6, 28, 9, 0), full_score=100, create_by=2),
            # 操作系统
            ExamBatch(course_id=2, batch_name="平时作业", batch_type=1, batch_weight=20,
                      exam_time=datetime(2026, 3, 18, 10, 0), full_score=100, create_by=2),
            ExamBatch(course_id=2, batch_name="期中考试", batch_type=3, batch_weight=30,
                      exam_time=datetime(2026, 4, 22, 14, 0), full_score=100, create_by=2),
            ExamBatch(course_id=2, batch_name="期末考试", batch_type=4, batch_weight=50,
                      exam_time=datetime(2026, 6, 30, 9, 0), full_score=100, create_by=2),
            # 数据结构
            ExamBatch(course_id=3, batch_name="平时作业", batch_type=1, batch_weight=25,
                      exam_time=datetime(2026, 3, 22, 10, 0), full_score=100, create_by=3),
            ExamBatch(course_id=3, batch_name="期中考试", batch_type=3, batch_weight=25,
                      exam_time=datetime(2026, 4, 28, 14, 0), full_score=100, create_by=3),
            ExamBatch(course_id=3, batch_name="期末考试", batch_type=4, batch_weight=50,
                      exam_time=datetime(2026, 6, 26, 9, 0), full_score=100, create_by=3),
        ]
        session.add_all(batches)
        session.commit()
        print(f"  考核批次: {len(batches)} 条")

        # ========== 10. 成绩记录（差异化：学霸/中等/挂科） ==========
        scores = [
            # ── 计算机网络 (batch 1~4) ──
            # 赵伟：优秀，各项高分
            ScoreRecord(course_id=1, student_id=1, batch_id=1,  score=92, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=1, batch_id=2,  score=88, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=1, batch_id=3,  score=85, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=1, batch_id=4,  score=90, is_pass=1, create_by=2),
            # 钱丽华：中等，成绩平稳
            ScoreRecord(course_id=1, student_id=2, batch_id=1,  score=75, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=2, batch_id=2,  score=70, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=2, batch_id=3,  score=72, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=2, batch_id=4,  score=68, is_pass=1, create_by=2),
            # 孙浩然：成绩下滑，期中到期末明显降低
            ScoreRecord(course_id=1, student_id=3, batch_id=1,  score=82, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=3, batch_id=2,  score=65, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=3, batch_id=3,  score=55, is_pass=0, create_by=2),
            ScoreRecord(course_id=1, student_id=3, batch_id=4,  score=48, is_pass=0, create_by=2),
            # 周敏：中上，稳定
            ScoreRecord(course_id=1, student_id=4, batch_id=1,  score=80, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=4, batch_id=2,  score=78, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=4, batch_id=3,  score=82, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=4, batch_id=4,  score=80, is_pass=1, create_by=2),
            # 吴天宇：低分飘过
            ScoreRecord(course_id=1, student_id=5, batch_id=1,  score=60, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=5, batch_id=2,  score=55, is_pass=0, create_by=2),
            ScoreRecord(course_id=1, student_id=5, batch_id=3,  score=52, is_pass=0, create_by=2),
            ScoreRecord(course_id=1, student_id=5, batch_id=4,  score=58, is_pass=0, create_by=2),
            # 郑小红：及格边缘
            ScoreRecord(course_id=1, student_id=8, batch_id=1,  score=68, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=8, batch_id=2,  score=62, is_pass=1, create_by=2),
            ScoreRecord(course_id=1, student_id=8, batch_id=3,  score=58, is_pass=0, create_by=2),
            ScoreRecord(course_id=1, student_id=8, batch_id=4,  score=65, is_pass=1, create_by=2),
            # ── 操作系统 (batch 5~7) ──
            # 赵伟：优秀
            ScoreRecord(course_id=2, student_id=1, batch_id=5,  score=95, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=1, batch_id=6,  score=88, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=1, batch_id=7,  score=92, is_pass=1, create_by=2),
            # 孙浩然：中等偏下
            ScoreRecord(course_id=2, student_id=3, batch_id=5,  score=65, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=3, batch_id=6,  score=58, is_pass=0, create_by=2),
            ScoreRecord(course_id=2, student_id=3, batch_id=7,  score=60, is_pass=1, create_by=2),
            # 周敏：良好
            ScoreRecord(course_id=2, student_id=4, batch_id=5,  score=78, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=4, batch_id=6,  score=80, is_pass=1, create_by=2),
            ScoreRecord(course_id=2, student_id=4, batch_id=7,  score=82, is_pass=1, create_by=2),
            # ── 数据结构 (batch 8~10) ──
            # 钱丽华：优秀（这门课特别好）
            ScoreRecord(course_id=3, student_id=2, batch_id=8,  score=95, is_pass=1, create_by=3),
            ScoreRecord(course_id=3, student_id=2, batch_id=9,  score=92, is_pass=1, create_by=3),
            ScoreRecord(course_id=3, student_id=2, batch_id=10, score=96, is_pass=1, create_by=3),
            # 吴天宇：挂科
            ScoreRecord(course_id=3, student_id=5, batch_id=8,  score=45, is_pass=0, create_by=3),
            ScoreRecord(course_id=3, student_id=5, batch_id=9,  score=38, is_pass=0, create_by=3),
            ScoreRecord(course_id=3, student_id=5, batch_id=10, score=42, is_pass=0, create_by=3),
            # 冯文博：进步型（从低到高）
            ScoreRecord(course_id=3, student_id=7, batch_id=8,  score=55, is_pass=0, create_by=3),
            ScoreRecord(course_id=3, student_id=7, batch_id=9,  score=72, is_pass=1, create_by=3),
            ScoreRecord(course_id=3, student_id=7, batch_id=10, score=85, is_pass=1, create_by=3),
            # 郑雨涵：中等
            ScoreRecord(course_id=3, student_id=6, batch_id=8,  score=70, is_pass=1, create_by=3),
            ScoreRecord(course_id=3, student_id=6, batch_id=9,  score=68, is_pass=1, create_by=3),
            ScoreRecord(course_id=3, student_id=6, batch_id=10, score=74, is_pass=1, create_by=3),
        ]
        session.add_all(scores)
        session.commit()
        print(f"  成绩记录: {len(scores)} 条")

        # ========== 11. 考勤记录（差异化：有人缺勤多，有人全勤） ==========
        from datetime import timedelta
        base = date(2026, 3, 3)
        attendances = []
        # 赵伟：全勤
        for i in range(6):
            d = base + timedelta(weeks=i)
            attendances.append(AttendanceRecord(course_id=1, student_id=1,
                                                attendance_date=d, status=0, create_by=2))
        # 钱丽华：迟到 2 次
        for i in range(6):
            d = base + timedelta(weeks=i)
            status = 1 if i in [2, 4] else 0
            remark = "迟到5分钟" if status == 1 else None
            attendances.append(AttendanceRecord(course_id=1, student_id=2,
                                                attendance_date=d, status=status, remark=remark, create_by=2))
        # 孙浩然：缺勤 3 次，严重
        for i in range(6):
            d = base + timedelta(weeks=i)
            status = 3 if i in [1, 3, 5] else 0
            remark = "未到" if status == 3 else None
            attendances.append(AttendanceRecord(course_id=1, student_id=3,
                                                attendance_date=d, status=status, remark=remark, create_by=2))
        # 吴天宇：请假 1 次 + 缺勤 1 次
        for i in range(6):
            d = base + timedelta(weeks=i)
            status = 4 if i == 0 else (3 if i == 4 else 0)
            remark = "病假" if status == 4 else ("未到" if status == 3 else None)
            attendances.append(AttendanceRecord(course_id=1, student_id=5,
                                                attendance_date=d, status=status, remark=remark, create_by=2))
        # 周敏：全勤
        for i in range(6):
            d = base + timedelta(weeks=i)
            attendances.append(AttendanceRecord(course_id=1, student_id=4,
                                                attendance_date=d, status=0, create_by=2))
        # 冯文博：迟到 1 次
        for i in range(4):
            d = base + timedelta(weeks=i)
            status = 1 if i == 2 else 0
            attendances.append(AttendanceRecord(course_id=3, student_id=7,
                                                attendance_date=d, status=status, create_by=3))
        # 郑小红：缺勤 1 次
        for i in range(4):
            d = base + timedelta(weeks=i)
            status = 3 if i == 3 else 0
            attendances.append(AttendanceRecord(course_id=1, student_id=8,
                                                attendance_date=d, status=status, create_by=2))
        session.add_all(attendances)
        session.commit()
        print(f"  考勤记录: {len(attendances)} 条")

        # ========== 12. 课堂互动（差异化） ==========
        interactions = [
            # 赵伟：互动积极，成绩好
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 5),
                              type=1, score=9.0, remark="回答准确", create_by=2),
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 12),
                              type=2, score=8.5, remark="小组讨论出色", create_by=2),
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 19),
                              type=3, score=9.5, create_by=2),
            InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 26),
                              type=4, score=8.0, create_by=2),
            # 钱丽华：中等
            InteractionRecord(course_id=1, student_id=2, interaction_date=date(2026, 3, 5),
                              type=1, score=7.0, create_by=2),
            InteractionRecord(course_id=1, student_id=2, interaction_date=date(2026, 3, 12),
                              type=3, score=7.5, create_by=2),
            # 孙浩然：互动少
            InteractionRecord(course_id=1, student_id=3, interaction_date=date(2026, 3, 5),
                              type=1, score=5.0, remark="回答不够完整", create_by=2),
            # 冯文博（数据结构课）：进步明显
            InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 4),
                              type=1, score=4.0, remark="表现一般", create_by=3),
            InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 11),
                              type=2, score=7.5, remark="讨论中进步", create_by=3),
            InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 18),
                              type=4, score=9.0, remark="测验成绩好", create_by=3),
        ]
        session.add_all(interactions)
        session.commit()
        print(f"  课堂互动: {len(interactions)} 条")

        # ========== 13. AI 题目（8道，覆盖题型） ==========
        questions = [
            AiQuestion(course_id=1, point_id=1, type=1,
                       content="OSI 参考模型共分为几层？",
                       options='["A. 5层","B. 6层","C. 7层","D. 8层"]',
                       correct_answer="C",
                       analysis="OSI 分为物理层、数据链路层、网络层、传输层、会话层、表示层、应用层共7层。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=2, type=1,
                       content="TCP/IP 协议栈中，负责数据路由的是哪一层？",
                       options='["A. 应用层","B. 传输层","C. 网络层","D. 数据链路层"]',
                       correct_answer="C",
                       analysis="网络层负责数据包的路由和转发。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=3, type=2,
                       content="以下哪些属于 TCP/IP 应用层协议？（多选）",
                       options='["A. HTTP","B. TCP","C. FTP","D. IP"]',
                       correct_answer='["A","C"]',
                       analysis="HTTP 和 FTP 属于应用层；TCP 属于传输层；IP 属于网络层。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=5, type=3,
                       content="TCP 三次握手中，第二次握手由服务器向客户端发送 SYN+ACK。",
                       options='["正确","错误"]',
                       correct_answer="正确",
                       analysis="服务器收到客户端 SYN 后，回复 SYN+ACK 确认。",
                       create_by=2),
            AiQuestion(course_id=1, point_id=7, type=3,
                       content="UDP 协议提供可靠的传输服务。",
                       options='["正确","错误"]',
                       correct_answer="错误",
                       analysis="UDP 是无连接、不可靠的协议，不保证数据可靠传输。",
                       create_by=2),
            AiQuestion(course_id=2, point_id=8, type=1,
                       content="进程从运行态转为就绪态，通常是因为什么？",
                       options='["A. 等待 I/O","B. 时间片用完","C. 主动调用 sleep","D. 被更高优先级抢占"]',
                       correct_answer="B",
                       analysis="时间片轮转调度中，当前进程时间片用完，从运行态回到就绪态。",
                       create_by=2),
            AiQuestion(course_id=3, point_id=11, type=4,
                       content="单向链表中，插入一个新节点的时间复杂度是____。",
                       correct_answer="O(1)",
                       analysis="在已知插入位置的前驱节点时，插入操作只需修改指针，时间复杂度 O(1)。",
                       create_by=3),
            AiQuestion(course_id=3, point_id=15, type=1,
                       content="快速排序的平均时间复杂度是？",
                       options='["A. O(n)","B. O(nlogn)","C. O(n^2)","D. O(logn)"]',
                       correct_answer="B",
                       analysis="快速排序平均时间复杂度为 O(nlogn)，最坏情况为 O(n^2)。",
                       create_by=3),
        ]
        session.add_all(questions)
        session.commit()
        print(f"  AI 题目: {len(questions)} 条")

        # ========== 14. 答题任务 & 关联 & 答题记录 ==========
        tasks = [
            AnswerTask(course_id=1, task_name="计算机网络单元测验1",
                       deadline=datetime(2026, 4, 30, 23, 59), status=1, create_by=2),
            AnswerTask(course_id=3, task_name="数据结构单元测验1",
                       deadline=datetime(2026, 4, 28, 23, 59), status=1, create_by=3),
        ]
        session.add_all(tasks)
        session.commit()

        task_questions = [
            TaskQuestion(task_id=1, question_id=1, sort_num=1),
            TaskQuestion(task_id=1, question_id=2, sort_num=2),
            TaskQuestion(task_id=1, question_id=3, sort_num=3),
            TaskQuestion(task_id=1, question_id=4, sort_num=4),
            TaskQuestion(task_id=1, question_id=5, sort_num=5),
            TaskQuestion(task_id=2, question_id=7, sort_num=1),
            TaskQuestion(task_id=2, question_id=8, sort_num=2),
        ]
        session.add_all(task_questions)
        session.commit()

        # 答题记录（差异化：有人全对，有人错几题）
        answers = [
            # 赵伟：全部答对
            StudentAnswerRecord(task_id=1, question_id=1, student_id=1, user_answer="C",  score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=2, student_id=1, user_answer="C",  score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=3, student_id=1, user_answer='["A","C"]', score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=4, student_id=1, user_answer="正确", score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=5, student_id=1, user_answer="错误", score=5, is_correct=1),
            # 钱丽华：对 3 题
            StudentAnswerRecord(task_id=1, question_id=1, student_id=2, user_answer="C",  score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=2, student_id=2, user_answer="B",  score=0, is_correct=0),
            StudentAnswerRecord(task_id=1, question_id=3, student_id=2, user_answer='["A"]', score=2, is_correct=0),
            StudentAnswerRecord(task_id=1, question_id=4, student_id=2, user_answer="正确", score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=5, student_id=2, user_answer="错误", score=5, is_correct=1),
            # 孙浩然：只对 2 题
            StudentAnswerRecord(task_id=1, question_id=1, student_id=3, user_answer="C",  score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=2, student_id=3, user_answer="A",  score=0, is_correct=0),
            StudentAnswerRecord(task_id=1, question_id=3, student_id=3, user_answer="B",  score=0, is_correct=0),
            StudentAnswerRecord(task_id=1, question_id=4, student_id=3, user_answer="正确", score=5, is_correct=1),
            StudentAnswerRecord(task_id=1, question_id=5, student_id=3, user_answer="正确", score=0, is_correct=0),
        ]
        session.add_all(answers)
        session.commit()
        print(f"  答题任务: {len(tasks)} 个，答题记录: {len(answers)} 条")

        # ========== 15. 评价维度 & 指标 ==========
        dimensions = [
            EvalDimension(course_id=1, dimension_name="学业成绩", description="考核成绩综合评价", sort_num=1),
            EvalDimension(course_id=1, dimension_name="学习态度", description="考勤和课堂参与度", sort_num=2),
            EvalDimension(course_id=3, dimension_name="学业成绩", description="考核成绩综合评价", sort_num=1),
            EvalDimension(course_id=3, dimension_name="学习态度", description="考勤和课堂参与度", sort_num=2),
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
            EvalIndex(dimension_id=3, index_name="期末成绩", weight=40,
                      score_rule='{"type":"direct","source":"score_record","batch_type":4}'),
            EvalIndex(dimension_id=3, index_name="平时成绩", weight=30,
                      score_rule='{"type":"direct","source":"score_record","batch_type":1}'),
            EvalIndex(dimension_id=3, index_name="期中成绩", weight=30,
                      score_rule='{"type":"direct","source":"score_record","batch_type":3}'),
            EvalIndex(dimension_id=4, index_name="出勤率", weight=50,
                      score_rule='{"type":"attendance","full_score":100}'),
            EvalIndex(dimension_id=4, index_name="课堂参与", weight=50,
                      score_rule='{"type":"interaction","full_score":100}'),
        ]
        session.add_all(indexes)
        session.commit()
        print(f"  评价维度: {len(dimensions)} 个，指标: {len(indexes)} 个")

        # ========== 16. 评价结果（差异化：优秀/良好/中等/及格/不及格） ==========
        eval_results = [
            # 计算机网络课 5 名学生
            StudentEvaluationResult(course_id=1, student_id=1, total_score=89.5, eval_level="优秀"),
            StudentEvaluationResult(course_id=1, student_id=2, total_score=72.0, eval_level="中等"),
            StudentEvaluationResult(course_id=1, student_id=3, total_score=52.5, eval_level="不及格"),
            StudentEvaluationResult(course_id=1, student_id=4, total_score=80.8, eval_level="良好"),
            StudentEvaluationResult(course_id=1, student_id=5, total_score=55.0, eval_level="不及格"),
            # 数据结构课
            StudentEvaluationResult(course_id=3, student_id=2, total_score=94.2, eval_level="优秀"),
            StudentEvaluationResult(course_id=3, student_id=7, total_score=70.5, eval_level="中等"),
        ]
        session.add_all(eval_results)
        session.commit()

        dimension_scores = [
            EvalDimensionScore(eval_id=1, dimension_id=1, dimension_score=90.0),
            EvalDimensionScore(eval_id=1, dimension_id=2, dimension_score=89.0),
            EvalDimensionScore(eval_id=2, dimension_id=1, dimension_score=71.5),
            EvalDimensionScore(eval_id=2, dimension_id=2, dimension_score=73.0),
            EvalDimensionScore(eval_id=3, dimension_id=1, dimension_score=48.5),
            EvalDimensionScore(eval_id=3, dimension_id=2, dimension_score=60.0),
            EvalDimensionScore(eval_id=4, dimension_id=1, dimension_score=80.5),
            EvalDimensionScore(eval_id=4, dimension_id=2, dimension_score=81.0),
            EvalDimensionScore(eval_id=5, dimension_id=1, dimension_score=56.0),
            EvalDimensionScore(eval_id=5, dimension_id=2, dimension_score=53.0),
            EvalDimensionScore(eval_id=6, dimension_id=3, dimension_score=94.0),
            EvalDimensionScore(eval_id=6, dimension_id=4, dimension_score=94.5),
            EvalDimensionScore(eval_id=7, dimension_id=3, dimension_score=70.0),
            EvalDimensionScore(eval_id=7, dimension_id=4, dimension_score=71.0),
        ]
        session.add_all(dimension_scores)
        session.commit()
        print(f"  评价结果: {len(eval_results)} 条，维度得分: {len(dimension_scores)} 条")

        # ========== 17. 知识点掌握度（差异化：强项弱项分明） ==========
        masteries = [
            # 赵伟：各知识点都高，但 UDP 稍弱
            KnowledgeMastery(course_id=1, student_id=1, point_id=1, mastery_score=92, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=2, mastery_score=88, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=3, mastery_score=85, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=5, mastery_score=90, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=6, mastery_score=86, mastery_level=3),
            KnowledgeMastery(course_id=1, student_id=1, point_id=7, mastery_score=78, mastery_level=2),
            # 钱丽华：中等，链路层弱
            KnowledgeMastery(course_id=1, student_id=2, point_id=1, mastery_score=72, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=2, point_id=2, mastery_score=68, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=2, point_id=3, mastery_score=55, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=2, point_id=5, mastery_score=70, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=2, point_id=6, mastery_score=65, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=2, point_id=7, mastery_score=60, mastery_level=2),
            # 孙浩然：普遍弱，传输层最差
            KnowledgeMastery(course_id=1, student_id=3, point_id=1, mastery_score=55, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=3, point_id=2, mastery_score=48, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=3, point_id=3, mastery_score=40, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=3, point_id=5, mastery_score=35, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=3, point_id=6, mastery_score=42, mastery_level=1),
            KnowledgeMastery(course_id=1, student_id=3, point_id=7, mastery_score=50, mastery_level=1),
            # 周敏：稳定中上
            KnowledgeMastery(course_id=1, student_id=4, point_id=1, mastery_score=82, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=4, point_id=2, mastery_score=78, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=4, point_id=5, mastery_score=80, mastery_level=2),
            KnowledgeMastery(course_id=1, student_id=4, point_id=6, mastery_score=75, mastery_level=2),
            # 冯文博（数据结构）：进步后中等偏上
            KnowledgeMastery(course_id=3, student_id=7, point_id=11, mastery_score=78, mastery_level=2),
            KnowledgeMastery(course_id=3, student_id=7, point_id=12, mastery_score=72, mastery_level=2),
            KnowledgeMastery(course_id=3, student_id=7, point_id=13, mastery_score=68, mastery_level=2),
            KnowledgeMastery(course_id=3, student_id=7, point_id=15, mastery_score=82, mastery_level=3),
            KnowledgeMastery(course_id=3, student_id=7, point_id=16, mastery_score=80, mastery_level=3),
            # 钱丽华（数据结构）：优秀
            KnowledgeMastery(course_id=3, student_id=2, point_id=11, mastery_score=95, mastery_level=3),
            KnowledgeMastery(course_id=3, student_id=2, point_id=12, mastery_score=90, mastery_level=3),
            KnowledgeMastery(course_id=3, student_id=2, point_id=13, mastery_score=92, mastery_level=3),
            KnowledgeMastery(course_id=3, student_id=2, point_id=15, mastery_score=96, mastery_level=3),
            KnowledgeMastery(course_id=3, student_id=2, point_id=16, mastery_score=94, mastery_level=3),
        ]
        session.add_all(masteries)
        session.commit()
        print(f"  知识点掌握度: {len(masteries)} 条")

        # ========== 18. 学情预警（差异化：不同原因不同等级） ==========
        warnings = [
            # 孙浩然：成绩下滑 + 缺勤多（高风险）
            StudyWarning(course_id=1, student_id=3,
                         warning_type="成绩下滑", warning_level=3,
                         warning_reason="期末成绩较平时大幅下滑，连续两次不及格",
                         handle_status=0),
            StudyWarning(course_id=1, student_id=3,
                         warning_type="缺勤超标", warning_level=3,
                         warning_reason="本学期缺勤3次，出勤率仅50%",
                         handle_status=0),
            # 吴天宇：多门课程成绩不及格（高风险）
            StudyWarning(course_id=1, student_id=5,
                         warning_type="成绩下滑", warning_level=2,
                         warning_reason="计算机网络期末不及格，平时成绩也在及格边缘",
                         handle_status=0),
            StudyWarning(course_id=3, student_id=5,
                         warning_type="成绩下滑", warning_level=3,
                         warning_reason="数据结构三次考核全部不及格，需重点关注",
                         handle_status=0),
            # 钱丽华：出勤偶尔迟到（低风险）
            StudyWarning(course_id=1, student_id=2,
                         warning_type="缺勤超标", warning_level=1,
                         warning_reason="本学期迟到2次，建议注意时间管理",
                         handle_status=0),
            # 郑小红：考勤有缺勤（低风险）
            StudyWarning(course_id=1, student_id=8,
                         warning_type="缺勤超标", warning_level=1,
                         warning_reason="本学期缺勤1次",
                         handle_status=0),
        ]
        session.add_all(warnings)
        session.commit()
        print(f"  学情预警: {len(warnings)} 条")

        # ========== 19. 学情画像 ==========
        profiles = [
            # 赵伟：综合优秀，学习态度好
            StudentProfile(course_id=1, student_id=1,
                           academic_score=90.0, attitude_score=95.0, progress_score=88.0,
                           total_profile_score=91.0,
                           study_tags="学习积极,各科均衡,自主学习强",
                           good_modules="网络体系结构,传输层",
                           weak_modules="数据链路层"),
            # 钱丽华：中等，数据结构突出
            StudentProfile(course_id=1, student_id=2,
                           academic_score=71.0, attitude_score=78.0, progress_score=70.0,
                           total_profile_score=73.0,
                           study_tags="稳定踏实,数据结构能力强",
                           good_modules="网络体系结构",
                           weak_modules="数据链路层"),
            StudentProfile(course_id=3, student_id=2,
                           academic_score=94.0, attitude_score=92.0, progress_score=90.0,
                           total_profile_score=92.5,
                           study_tags="该科目优秀",
                           good_modules="线性结构,树与图,排序算法",
                           weak_modules=""),
            # 孙浩然：下滑严重
            StudentProfile(course_id=1, student_id=3,
                           academic_score=48.0, attitude_score=52.0, progress_score=40.0,
                           total_profile_score=46.5,
                           study_tags="成绩下滑,缺勤多,需预警关注",
                           good_modules="",
                           weak_modules="网络体系结构,数据链路层,传输层"),
            # 周敏：稳定良好
            StudentProfile(course_id=1, student_id=4,
                           academic_score=80.0, attitude_score=92.0, progress_score=82.0,
                           total_profile_score=83.5,
                           study_tags="学习态度好,稳定",
                           good_modules="网络体系结构,传输层",
                           weak_modules="数据链路层"),
            # 吴天宇：多门课不理想
            StudentProfile(course_id=1, student_id=5,
                           academic_score=55.0, attitude_score=60.0, progress_score=45.0,
                           total_profile_score=53.0,
                           study_tags="多门课程成绩不理想",
                           good_modules="",
                           weak_modules="网络体系结构,数据链路层,传输层"),
            # 冯文博：进步型
            StudentProfile(course_id=3, student_id=7,
                           academic_score=70.0, attitude_score=85.0, progress_score=82.0,
                           total_profile_score=78.0,
                           study_tags="进步明显,后半学期发力",
                           good_modules="排序算法",
                           weak_modules="树与图"),
        ]
        session.add_all(profiles)
        session.commit()
        print(f"  学情画像: {len(profiles)} 条")

        # ========== 20. 操作日志 ==========
        logs = [
            SysOperationLog(user_id=1, module="用户管理", operation="新增",
                            content="创建教师账号 teacher3（陈晓芳）", ip_address="127.0.0.1"),
            SysOperationLog(user_id=1, module="数据管理", operation="导入",
                            content="导入2025-2026-1学期计算机网络课程成绩数据", ip_address="127.0.0.1"),
            SysOperationLog(user_id=1, module="数据管理", operation="导入",
                            content="导入2025-2026-1学期操作系统课程成绩数据", ip_address="127.0.0.1"),
            SysOperationLog(user_id=2, module="课程管理", operation="新增",
                            content="新增课程：计算机网络 CS3001", ip_address="127.0.0.1"),
            SysOperationLog(user_id=2, module="课程管理", operation="新增",
                            content="新增课程：操作系统 CS3002", ip_address="127.0.0.1"),
            SysOperationLog(user_id=2, module="题库管理", operation="新增",
                            content="批量导入计算机网络试题 5 道", ip_address="127.0.0.1"),
            SysOperationLog(user_id=2, module="考试管理", operation="发布",
                            content="发布计算机网络单元测验1", ip_address="127.0.0.1"),
            SysOperationLog(user_id=3, module="课程管理", operation="新增",
                            content="新增课程：数据结构 CS3003", ip_address="127.0.0.1"),
            SysOperationLog(user_id=3, module="题库管理", operation="新增",
                            content="批量导入数据结构试题 2 道", ip_address="127.0.0.1"),
            SysOperationLog(user_id=1, module="用户管理", operation="编辑",
                            content="修改教师李明远职称信息", ip_address="127.0.0.1"),
        ]
        session.add_all(logs)
        session.commit()
        print(f"  操作日志: {len(logs)} 条")

    print("[seed] 全部演示数据已灌入")


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入演示数据")
    parser.add_argument("--reset", action="store_true", help="删库重建后再灌入")
    args = parser.parse_args()
    if args.reset:
        reset()
    seed()


if __name__ == "__main__":
    main()
