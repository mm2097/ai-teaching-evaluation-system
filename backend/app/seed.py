"""Seed 脚本：灌入丰富的差异化演示数据。

用法:
    python -m app.seed              # 灌入数据（表不存在会自动建）
    python -m app.seed --reset      # 删库重建后再灌入（推荐）
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from sqlmodel import Session, SQLModel, select

from app.core.database import engine, init_db
from app.core.security import hash_password
from app.models import (
    SysUser, SysRole, Teacher, Student, ClassInfo, Course, CourseStudent,
    KnowledgeModule, KnowledgePoint,
    AttendanceRecord, InteractionRecord,
    ExamBatch, ScoreRecord,
    IndividualScore, AttendanceSheet, CourseTestDetail,
    AiQuestion, AnswerTask, AnswerTaskClass, TaskQuestion, StudentAnswerRecord,
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
        for user in users:
            user.password = hash_password(user.password)
        session.add_all(users)
        session.commit()
        print(f"  用户: {len(users)} 条")

        # 测试数据学生用户（47人，来自"测试数据"文件夹的三个 Excel 文件）
        test_student_users = [
            # ── 软件1801 班（25人）──
            SysUser(username="201726010101", password="123456", real_name="孔祥宁", role_id=3, status=1),
            SysUser(username="201803030311", password="123456", real_name="杨伯昊", role_id=3, status=1),
            SysUser(username="201826010102", password="123456", real_name="徐颖", role_id=3, status=1),
            SysUser(username="201826010103", password="123456", real_name="甘凌志", role_id=3, status=1),
            SysUser(username="201826010104", password="123456", real_name="陈佳伟", role_id=3, status=1),
            SysUser(username="201826010105", password="123456", real_name="张峻宇", role_id=3, status=1),
            SysUser(username="201826010106", password="123456", real_name="蔡君浩", role_id=3, status=1),
            SysUser(username="201826010109", password="123456", real_name="钟婧", role_id=3, status=1),
            SysUser(username="201826010112", password="123456", real_name="丁嘉欣", role_id=3, status=1),
            SysUser(username="201826010113", password="123456", real_name="肖云杰", role_id=3, status=1),
            SysUser(username="201826010114", password="123456", real_name="张馀玎", role_id=3, status=1),
            SysUser(username="201826010115", password="123456", real_name="詹家坤", role_id=3, status=1),
            SysUser(username="201826010117", password="123456", real_name="张楠", role_id=3, status=1),
            SysUser(username="201826010118", password="123456", real_name="何楚强", role_id=3, status=1),
            SysUser(username="201826010119", password="123456", real_name="李雨辰", role_id=3, status=1),
            SysUser(username="201826010120", password="123456", real_name="李星沛", role_id=3, status=1),
            SysUser(username="201826010122", password="123456", real_name="吴催波", role_id=3, status=1),
            SysUser(username="201826010123", password="123456", real_name="周兴宇", role_id=3, status=1),
            SysUser(username="201826010124", password="123456", real_name="杨家豪", role_id=3, status=1),
            SysUser(username="201826010126", password="123456", real_name="梁金子", role_id=3, status=1),
            SysUser(username="201826010127", password="123456", real_name="李瀚林", role_id=3, status=1),
            SysUser(username="201826010128", password="123456", real_name="徐静茹", role_id=3, status=1),
            SysUser(username="201826010129", password="123456", real_name="钱辰", role_id=3, status=1),
            SysUser(username="201826010130", password="123456", real_name="加拉力丁·依马木", role_id=3, status=1),
            SysUser(username="201829010201", password="123456", real_name="李世颂", role_id=3, status=1),
            # ── 软件1803 班（22人）──
            SysUser(username="201808030406", password="123456", real_name="赵双艺", role_id=3, status=1),
            SysUser(username="201808030408", password="123456", real_name="黄舟瑜", role_id=3, status=1),
            SysUser(username="201826010302", password="123456", real_name="张佳妮", role_id=3, status=1),
            SysUser(username="201826010303", password="123456", real_name="李元哲", role_id=3, status=1),
            SysUser(username="201826010304", password="123456", real_name="虞绮春", role_id=3, status=1),
            SysUser(username="201826010305", password="123456", real_name="张智清", role_id=3, status=1),
            SysUser(username="201826010306", password="123456", real_name="彭浩宇", role_id=3, status=1),
            SysUser(username="201826010307", password="123456", real_name="潘星辰", role_id=3, status=1),
            SysUser(username="201826010308", password="123456", real_name="沈伟峰", role_id=3, status=1),
            SysUser(username="201826010310", password="123456", real_name="杨晓迪", role_id=3, status=1),
            SysUser(username="201826010311", password="123456", real_name="王成龙", role_id=3, status=1),
            SysUser(username="201826010313", password="123456", real_name="杨佳", role_id=3, status=1),
            SysUser(username="201826010316", password="123456", real_name="陈扬霈", role_id=3, status=1),
            SysUser(username="201826010318", password="123456", real_name="李俊", role_id=3, status=1),
            SysUser(username="201826010319", password="123456", real_name="李菲菲", role_id=3, status=1),
            SysUser(username="201826010321", password="123456", real_name="宁君辉", role_id=3, status=1),
            SysUser(username="201826010322", password="123456", real_name="胡亮", role_id=3, status=1),
            SysUser(username="201826010323", password="123456", real_name="谭晓杰", role_id=3, status=1),
            SysUser(username="201826010325", password="123456", real_name="刘海天", role_id=3, status=1),
            SysUser(username="201826010326", password="123456", real_name="李明光", role_id=3, status=1),
            SysUser(username="201826010327", password="123456", real_name="陈熙麟", role_id=3, status=1),
            SysUser(username="201826010329", password="123456", real_name="江北辰", role_id=3, status=1),
            # ── 软件1802 班（21人，来自期中考试文件的 软件1802 Sheet，header在row2）──
            SysUser(username="201713010118", password="123456", real_name="郭晗婕", role_id=3, status=1),
            SysUser(username="201804050215", password="123456", real_name="鲍炜杰", role_id=3, status=1),
            SysUser(username="201804061214", password="123456", real_name="方浩楠", role_id=3, status=1),
            SysUser(username="201826010201", password="123456", real_name="高伊格", role_id=3, status=1),
            SysUser(username="201826010203", password="123456", real_name="梁耀升", role_id=3, status=1),
            SysUser(username="201826010204", password="123456", real_name="潘琳", role_id=3, status=1),
            SysUser(username="201826010206", password="123456", real_name="李锦浩", role_id=3, status=1),
            SysUser(username="201826010209", password="123456", real_name="陈柏宇", role_id=3, status=1),
            SysUser(username="201826010214", password="123456", real_name="洪绵权", role_id=3, status=1),
            SysUser(username="201826010215", password="123456", real_name="刘大卫", role_id=3, status=1),
            SysUser(username="201826010216", password="123456", real_name="肖欣", role_id=3, status=1),
            SysUser(username="201826010217", password="123456", real_name="殷浩翔", role_id=3, status=1),
            SysUser(username="201826010218", password="123456", real_name="邹智翼", role_id=3, status=1),
            SysUser(username="201826010219", password="123456", real_name="雷佳晨", role_id=3, status=1),
            SysUser(username="201826010220", password="123456", real_name="马诗丹", role_id=3, status=1),
            SysUser(username="201826010222", password="123456", real_name="曹芊", role_id=3, status=1),
            SysUser(username="201826010223", password="123456", real_name="唐诗远", role_id=3, status=1),
            SysUser(username="201826010227", password="123456", real_name="刘佳雨", role_id=3, status=1),
            SysUser(username="201826010228", password="123456", real_name="吴优", role_id=3, status=1),
            SysUser(username="201826010229", password="123456", real_name="鄢蝶", role_id=3, status=1),
            SysUser(username="201826010230", password="123456", real_name="麦麦提·阿卜杜赛米", role_id=3, status=1),
        ]
        for user in test_student_users:
            user.password = hash_password(user.password)
        session.add_all(test_student_users)
        session.commit()
        print(f"  测试学生用户: {len(test_student_users)} 条")

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
            ClassInfo(class_name="计科2401班", college="计算机学院", major="计算机科学与技术", grade="2024级"),
            ClassInfo(class_name="计科2402班", college="计算机学院", major="计算机科学与技术", grade="2024级"),
            ClassInfo(class_name="软工2401班", college="计算机学院", major="软件工程", grade="2024级"),
            ClassInfo(class_name="计科2301班", college="计算机学院", major="计算机科学与技术", grade="2023级"),
            ClassInfo(class_name="数统2401班", college="数学与统计学院", major="数学与应用数学", grade="2024级"),
        ]
        session.add_all(classes)
        session.commit()
        print(f"  班级: {len(classes)} 条")

        # 测试数据班级（对应模板中 软件1801/1802/1803 三个 Sheet）
        test_classes = [
            ClassInfo(class_name="软件1801班", college="计算机学院", major="软件工程", grade="2018级"),
            ClassInfo(class_name="软件1802班", college="计算机学院", major="软件工程", grade="2018级"),
            ClassInfo(class_name="软件1803班", college="计算机学院", major="软件工程", grade="2018级"),
        ]
        session.add_all(test_classes)
        session.commit()
        print(f"  测试班级: {len(test_classes)} 条")

        # ========== 5. 学生（10人，分散在不同班级、不同性别） ==========
        students = [
            Student(student_no="2024001001", real_name="赵伟", gender=1,
                    class_id=6, user_id=5, phone="13900000001", email="zw@stu.edu.cn"),
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

        # 测试数据学生记录（47人，user_id 对应上一批测试用户 15~61）
        # 演示联调：student（赵伟）与 201726010101（孔祥宁）同属软件1801（class_id=6）
        # 其余 Excel 模板学生：6=软件1801班，7=软件1802班，8=软件1803班
        test_students = [
            # ── 软件1801（演示账号 student 同班，1人）──
            Student(student_no="201726010101", real_name="孔祥宁", gender=1, class_id=6, user_id=15),
            # ── 软件1801 班（24人，user_id 16~39）──
            Student(student_no="201803030311", real_name="杨伯昊", gender=1, class_id=6, user_id=16),
            Student(student_no="201826010102", real_name="徐颖",    gender=0, class_id=6, user_id=17),
            Student(student_no="201826010103", real_name="甘凌志",  gender=1, class_id=6, user_id=18),
            Student(student_no="201826010104", real_name="陈佳伟",  gender=1, class_id=6, user_id=19),
            Student(student_no="201826010105", real_name="张峻宇",  gender=1, class_id=6, user_id=20),
            Student(student_no="201826010106", real_name="蔡君浩",  gender=1, class_id=6, user_id=21),
            Student(student_no="201826010109", real_name="钟婧",    gender=0, class_id=6, user_id=22),
            Student(student_no="201826010112", real_name="丁嘉欣",  gender=0, class_id=6, user_id=23),
            Student(student_no="201826010113", real_name="肖云杰",  gender=1, class_id=6, user_id=24),
            Student(student_no="201826010114", real_name="张馀玎",  gender=1, class_id=6, user_id=25),
            Student(student_no="201826010115", real_name="詹家坤",  gender=1, class_id=6, user_id=26),
            Student(student_no="201826010117", real_name="张楠",    gender=0, class_id=6, user_id=27),
            Student(student_no="201826010118", real_name="何楚强",  gender=1, class_id=6, user_id=28),
            Student(student_no="201826010119", real_name="李雨辰",  gender=0, class_id=6, user_id=29),
            Student(student_no="201826010120", real_name="李星沛",  gender=1, class_id=6, user_id=30),
            Student(student_no="201826010122", real_name="吴催波",  gender=1, class_id=6, user_id=31),
            Student(student_no="201826010123", real_name="周兴宇",  gender=1, class_id=6, user_id=32),
            Student(student_no="201826010124", real_name="杨家豪",  gender=1, class_id=6, user_id=33),
            Student(student_no="201826010126", real_name="梁金子",  gender=0, class_id=6, user_id=34),
            Student(student_no="201826010127", real_name="李瀚林",  gender=1, class_id=6, user_id=35),
            Student(student_no="201826010128", real_name="徐静茹",  gender=0, class_id=6, user_id=36),
            Student(student_no="201826010129", real_name="钱辰",    gender=1, class_id=6, user_id=37),
            Student(student_no="201826010130", real_name="加拉力丁·依马木", gender=1, class_id=6, user_id=38),
            Student(student_no="201829010201", real_name="李世颂",  gender=1, class_id=6, user_id=39),
            # ── 软件1803 班（22人，user_id 40~61）──
            Student(student_no="201808030406", real_name="赵双艺",  gender=0, class_id=8, user_id=40),
            Student(student_no="201808030408", real_name="黄舟瑜",  gender=1, class_id=8, user_id=41),
            Student(student_no="201826010302", real_name="张佳妮",  gender=0, class_id=8, user_id=42),
            Student(student_no="201826010303", real_name="李元哲",  gender=1, class_id=8, user_id=43),
            Student(student_no="201826010304", real_name="虞绮春",  gender=0, class_id=8, user_id=44),
            Student(student_no="201826010305", real_name="张智清",  gender=1, class_id=8, user_id=45),
            Student(student_no="201826010306", real_name="彭浩宇",  gender=1, class_id=8, user_id=46),
            Student(student_no="201826010307", real_name="潘星辰",  gender=1, class_id=8, user_id=47),
            Student(student_no="201826010308", real_name="沈伟峰",  gender=1, class_id=8, user_id=48),
            Student(student_no="201826010310", real_name="杨晓迪",  gender=0, class_id=8, user_id=49),
            Student(student_no="201826010311", real_name="王成龙",  gender=1, class_id=8, user_id=50),
            Student(student_no="201826010313", real_name="杨佳",    gender=0, class_id=8, user_id=51),
            Student(student_no="201826010316", real_name="陈扬霈",  gender=1, class_id=8, user_id=52),
            Student(student_no="201826010318", real_name="李俊",    gender=1, class_id=8, user_id=53),
            Student(student_no="201826010319", real_name="李菲菲",  gender=0, class_id=8, user_id=54),
            Student(student_no="201826010321", real_name="宁君辉",  gender=1, class_id=8, user_id=55),
            Student(student_no="201826010322", real_name="胡亮",    gender=1, class_id=8, user_id=56),
            Student(student_no="201826010323", real_name="谭晓杰",  gender=1, class_id=8, user_id=57),
            Student(student_no="201826010325", real_name="刘海天",  gender=1, class_id=8, user_id=58),
            Student(student_no="201826010326", real_name="李明光",  gender=1, class_id=8, user_id=59),
            Student(student_no="201826010327", real_name="陈熙麟",  gender=1, class_id=8, user_id=60),
            Student(student_no="201826010329", real_name="江北辰",  gender=1, class_id=8, user_id=61),
            # ── 软件1802 班（21人，user_id 62~82）──
            Student(student_no="201713010118", real_name="郭晗婕",  gender=0, class_id=7, user_id=62),
            Student(student_no="201804050215", real_name="鲍炜杰",  gender=1, class_id=7, user_id=63),
            Student(student_no="201804061214", real_name="方浩楠",  gender=1, class_id=7, user_id=64),
            Student(student_no="201826010201", real_name="高伊格",  gender=1, class_id=7, user_id=65),
            Student(student_no="201826010203", real_name="梁耀升",  gender=1, class_id=7, user_id=66),
            Student(student_no="201826010204", real_name="潘琳",    gender=0, class_id=7, user_id=67),
            Student(student_no="201826010206", real_name="李锦浩",  gender=1, class_id=7, user_id=68),
            Student(student_no="201826010209", real_name="陈柏宇",  gender=1, class_id=7, user_id=69),
            Student(student_no="201826010214", real_name="洪绵权",  gender=1, class_id=7, user_id=70),
            Student(student_no="201826010215", real_name="刘大卫",  gender=1, class_id=7, user_id=71),
            Student(student_no="201826010216", real_name="肖欣",    gender=0, class_id=7, user_id=72),
            Student(student_no="201826010217", real_name="殷浩翔",  gender=1, class_id=7, user_id=73),
            Student(student_no="201826010218", real_name="邹智翼",  gender=1, class_id=7, user_id=74),
            Student(student_no="201826010219", real_name="雷佳晨",  gender=1, class_id=7, user_id=75),
            Student(student_no="201826010220", real_name="马诗丹",  gender=0, class_id=7, user_id=76),
            Student(student_no="201826010222", real_name="曹芊",    gender=0, class_id=7, user_id=77),
            Student(student_no="201826010223", real_name="唐诗远",  gender=1, class_id=7, user_id=78),
            Student(student_no="201826010227", real_name="刘佳雨",  gender=0, class_id=7, user_id=79),
            Student(student_no="201826010228", real_name="吴优",    gender=0, class_id=7, user_id=80),
            Student(student_no="201826010229", real_name="鄢蝶",    gender=0, class_id=7, user_id=81),
            Student(student_no="201826010230", real_name="麦麦提·阿卜杜赛米", gender=1, class_id=7, user_id=82),
        ]
        session.add_all(test_students)
        session.commit()
        print(f"  测试学生: {len(test_students)} 条")

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
            # 数据结构：6人选（含赵伟，便于看到 teacher2 发布的同班测验）
            CourseStudent(course_id=3, student_id=1),
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

        # 测试数据学生全部选修计算机网络（student_id 11~78，共68人）
        test_course_students = [
            CourseStudent(course_id=1, student_id=sid) for sid in range(11, 79)
        ]
        session.add_all(test_course_students)
        session.commit()
        print(f"  测试选修关系: {len(test_course_students)} 条")

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
                      semester="2025-2026-2", full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="实验报告", batch_type=2, batch_weight=15,
                      semester="2025-2026-2", full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期中考试", batch_type=3, batch_weight=25,
                      semester="2025-2026-2", full_score=100, create_by=2),
            ExamBatch(course_id=1, batch_name="期末考试", batch_type=4, batch_weight=40,
                      semester="2025-2026-2", full_score=100, create_by=2),
            # 操作系统
            ExamBatch(course_id=2, batch_name="平时作业", batch_type=1, batch_weight=20,
                      semester="2025-2026-2", full_score=100, create_by=2),
            ExamBatch(course_id=2, batch_name="期中考试", batch_type=3, batch_weight=30,
                      semester="2025-2026-2", full_score=100, create_by=2),
            ExamBatch(course_id=2, batch_name="期末考试", batch_type=4, batch_weight=50,
                      semester="2025-2026-2", full_score=100, create_by=2),
            # 数据结构
            ExamBatch(course_id=3, batch_name="平时作业", batch_type=1, batch_weight=25,
                      semester="2025-2026-2", full_score=100, create_by=3),
            ExamBatch(course_id=3, batch_name="期中考试", batch_type=3, batch_weight=25,
                      semester="2025-2026-2", full_score=100, create_by=3),
            ExamBatch(course_id=3, batch_name="期末考试", batch_type=4, batch_weight=50,
                      semester="2025-2026-2", full_score=100, create_by=3),
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

        # ========== 12. 课堂互动（已禁用 - 功能暂不展示） ==========
        # interactions = [
        #     # 赵伟：互动积极，成绩好
        #     InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 5),
        #                       type=1, score=9.0, remark="回答准确", create_by=2),
        #     InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 12),
        #                       type=2, score=8.5, remark="小组讨论出色", create_by=2),
        #     InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 19),
        #                       type=3, score=9.5, create_by=2),
        #     InteractionRecord(course_id=1, student_id=1, interaction_date=date(2026, 3, 26),
        #                       type=4, score=8.0, create_by=2),
        #     # 钱丽华：中等
        #     InteractionRecord(course_id=1, student_id=2, interaction_date=date(2026, 3, 5),
        #                       type=1, score=7.0, create_by=2),
        #     InteractionRecord(course_id=1, student_id=2, interaction_date=date(2026, 3, 12),
        #                       type=3, score=7.5, create_by=2),
        #     # 孙浩然：互动少
        #     InteractionRecord(course_id=1, student_id=3, interaction_date=date(2026, 3, 5),
        #                       type=1, score=5.0, remark="回答不够完整", create_by=2),
        #     # 冯文博（数据结构课）：进步明显
        #     InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 4),
        #                       type=1, score=4.0, remark="表现一般", create_by=3),
        #     InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 11),
        #                       type=2, score=7.5, remark="讨论中进步", create_by=3),
        #     InteractionRecord(course_id=3, student_id=7, interaction_date=date(2026, 3, 18),
        #                       type=4, score=9.0, remark="测验成绩好", create_by=3),
        # ]
        # session.add_all(interactions)
        # session.commit()
        # print(f"  课堂互动: {len(interactions)} 条")

        # ========== 13. AI 题目（8道，覆盖题型） ==========
        questions = [
            AiQuestion(course_id=1, point_id=1, type=1,
                       content="OSI 参考模型共分为几层？",
                       options='["A. 5层","B. 6层","C. 7层","D. 8层"]',
                       correct_answer="C",
                       analysis="OSI 分为物理层、数据链路层、网络层、传输层、会话层、表示层、应用层共7层。",
                       difficulty="easy",
                       create_by=2),
            AiQuestion(course_id=1, point_id=2, type=1,
                       content="TCP/IP 协议栈中，负责数据路由的是哪一层？",
                       options='["A. 应用层","B. 传输层","C. 网络层","D. 数据链路层"]',
                       correct_answer="C",
                       analysis="网络层负责数据包的路由和转发。",
                       difficulty="easy",
                       create_by=2),
            AiQuestion(course_id=1, point_id=3, type=2,
                       content="以下哪些属于 TCP/IP 应用层协议？（多选）",
                       options='["A. HTTP","B. TCP","C. FTP","D. IP"]',
                       correct_answer='["A","C"]',
                       analysis="HTTP 和 FTP 属于应用层；TCP 属于传输层；IP 属于网络层。",
                       difficulty="medium",
                       create_by=2),
            AiQuestion(course_id=1, point_id=5, type=3,
                       content="TCP 三次握手中，第二次握手由服务器向客户端发送 SYN+ACK。",
                       options='["正确","错误"]',
                       correct_answer="正确",
                       analysis="服务器收到客户端 SYN 后，回复 SYN+ACK 确认。",
                       difficulty="medium",
                       create_by=2),
            AiQuestion(course_id=1, point_id=7, type=3,
                       content="UDP 协议提供可靠的传输服务。",
                       options='["正确","错误"]',
                       correct_answer="错误",
                       analysis="UDP 是无连接、不可靠的协议，不保证数据可靠传输。",
                       difficulty="easy",
                       create_by=2),
            AiQuestion(course_id=2, point_id=8, type=1,
                       content="进程从运行态转为就绪态，通常是因为什么？",
                       options='["A. 等待 I/O","B. 时间片用完","C. 主动调用 sleep","D. 被更高优先级抢占"]',
                       correct_answer="B",
                       analysis="时间片轮转调度中，当前进程时间片用完，从运行态回到就绪态。",
                       difficulty="medium",
                       create_by=2),
            AiQuestion(course_id=3, point_id=11, type=4,
                       content="单向链表中，插入一个新节点的时间复杂度是____。",
                       correct_answer="O(1)",
                       analysis="在已知插入位置的前驱节点时，插入操作只需修改指针，时间复杂度 O(1)。",
                       difficulty="medium",
                       create_by=3),
            AiQuestion(course_id=3, point_id=15, type=1,
                       content="快速排序的平均时间复杂度是？",
                       options='["A. O(n)","B. O(nlogn)","C. O(n^2)","D. O(logn)"]',
                       correct_answer="B",
                       analysis="快速排序平均时间复杂度为 O(nlogn)，最坏情况为 O(n^2)。",
                       difficulty="medium",
                       create_by=3),
            # 简答题种子题
            AiQuestion(course_id=1, point_id=5, type=5,
                       content="简述 TCP 三次握手的过程及其必要性。",
                       correct_answer="TCP 三次握手用于建立可靠连接：第一次握手客户端发送 SYN，seq=x，进入 SYN_SENT 状态；第二次握手服务器收到后回复 SYN+ACK，seq=y，ack=x+1，进入 SYN_RCVD 状态；第三次握手客户端发送 ACK，ack=y+1，双方进入 ESTABLISHED 状态。三次握手的必要性在于确认双方的收发能力正常，防止已失效的连接请求报文突然到达服务器造成资源浪费。",
                       analysis="评分要点：1) 准确描述三次握手每一步的报文和状态变化；2) 说明 SYN/ACK 的作用；3) 解释三次握手为何不是两次或四次。",
                       difficulty="hard",
                       create_by=2),
            AiQuestion(course_id=3, point_id=13, type=5,
                       content="请解释什么是二叉树，并说明其基本性质。",
                       correct_answer="二叉树是每个节点最多有两个子节点（左子树和右子树）的树形数据结构。基本性质：1) 第 i 层最多有 2^(i-1) 个节点；2) 深度为 k 的二叉树最多有 2^k-1 个节点；3) 叶子节点数等于度为 2 的节点数加 1，即 n0=n2+1；4) 完全二叉树中 n 个节点的深度为 floor(log2(n))+1。",
                       analysis="评分要点：1) 正确定义二叉树（最多两个子节点）；2) 至少列出两条基本性质；3) 提到子树有左右之分。",
                       difficulty="medium",
                       create_by=3),
        ]
        session.add_all(questions)
        session.commit()
        print(f"  AI 题目: {len(questions)} 条")

        # ========== 14. 答题任务 & 关联 & 答题记录 ==========
        tasks = [
            AnswerTask(course_id=1, task_name="计算机网络单元测验1",
                       deadline=datetime(2026, 4, 30, 23, 59), status=1, allow_review=1,
                       publish_time=datetime(2026, 3, 1, 9, 0), create_by=2),
            AnswerTask(course_id=3, task_name="数据结构单元测验1",
                       deadline=datetime(2026, 4, 28, 23, 59), status=1, allow_review=1,
                       publish_time=datetime(2026, 3, 1, 9, 0), create_by=3),
        ]
        session.add_all(tasks)
        session.commit()

        task_classes = [
            AnswerTaskClass(task_id=1, class_id=6),
            AnswerTaskClass(task_id=2, class_id=6),
        ]
        session.add_all(task_classes)
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


# ========== 智能分析模块预注入数据 ==========
# 为所有测试学生注入学情画像、成绩趋势预测、知识点掌握度、异常学情预警数据
# 用法: python -m app.seed --inject-analysis


def _student_tier(student_id: int) -> int:
    """根据 student_id 确定性分配档位（0=S优秀 ~ 4=D不及格）。"""
    # 使用简单取模分配，均匀分布
    tiers = [0, 1, 1, 2, 2, 3, 4]  # 7个一组: S, A, A, B, B, C, D
    return tiers[(student_id - 11) % 7]


def _tier_score_range(tier: int) -> tuple[int, int]:
    """档位 → 成绩范围 (min, max)。"""
    ranges = {
        0: (86, 98),   # S: 优秀
        1: (75, 88),   # A: 良好
        2: (62, 78),   # B: 中等
        3: (48, 66),   # C: 及格边缘
        4: (28, 52),   # D: 不及格
    }
    return ranges.get(tier, (62, 78))


def _tier_trend(tier: int, student_id: int) -> str:
    """档位 → 成绩趋势（up/down/flat），结合 ID 增加变化。"""
    if tier == 0:
        # 优秀的：大部分稳定或上升
        return "up" if student_id % 3 == 0 else "flat"
    elif tier == 1:
        return "flat" if student_id % 2 == 0 else "up"
    elif tier == 2:
        opts = ["flat", "up", "down"]
        return opts[student_id % 3]
    elif tier == 3:
        return "down" if student_id % 2 == 0 else "flat"
    else:
        # D 级：大多下滑
        return "down" if student_id % 3 != 0 else "flat"


def _deterministic_scores(student_id: int, tier: int, trend: str) -> list[float]:
    """生成 4 次考核成绩（平时作业/实验报告/期中/期末），确定性但差异化。"""
    lo, hi = _tier_score_range(tier)
    mid = (lo + hi) / 2
    # 使用 student_id 的各位数字之和作为随机种子
    seed_val = sum(int(c) for c in str(student_id) if c.isdigit())

    if trend == "up":
        # 成绩逐步上升
        base = lo + (seed_val % 8)
        return [
            round(base + (seed_val % 3), 1),
            round(base + 4 + ((seed_val // 10) % 5), 1),
            round(base + 8 + ((seed_val // 7) % 5), 1),
            round(min(hi + 2, base + 14 + ((seed_val // 3) % 6)), 1),
        ]
    elif trend == "down":
        # 成绩逐步下滑
        base = hi - (seed_val % 8)
        return [
            round(base - ((seed_val // 7) % 5), 1),
            round(base - 4 - ((seed_val // 3) % 5), 1),
            round(base - 8 - (seed_val % 5), 1),
            round(max(lo - 2, base - 14 - ((seed_val // 10) % 6)), 1),
        ]
    else:
        # 稳定波动
        return [
            round(mid + ((seed_val + i * 3) % 7) - 3, 1)
            for i in range(4)
        ]


def _deterministic_attendance(student_id: int, tier: int) -> list[dict]:
    """生成 6 次考勤记录（确定性、差异化）。"""
    events = []
    seed_val = sum(int(c) for c in str(student_id) if c.isdigit())
    weeks = [date(2026, 3, 3) + timedelta(weeks=i) for i in range(6)]

    # 不同档位缺勤/迟到概率不同
    if tier == 0:  # S: 全勤
        for w in weeks:
            events.append({"date": w, "status": 0, "remark": None})
    elif tier == 1:  # A: 偶尔迟到
        for i, w in enumerate(weeks):
            if (seed_val + i) % 7 == 0:
                events.append({"date": w, "status": 1, "remark": "迟到5分钟"})
            else:
                events.append({"date": w, "status": 0, "remark": None})
    elif tier == 2:  # B: 1-2次迟到或缺勤
        for i, w in enumerate(weeks):
            if (seed_val + i) % 5 == 0:
                events.append({"date": w, "status": 3, "remark": "未到"})
            elif (seed_val + i) % 7 == 0:
                events.append({"date": w, "status": 1, "remark": "迟到"})
            else:
                events.append({"date": w, "status": 0, "remark": None})
    elif tier == 3:  # C: 2-3次缺勤
        for i, w in enumerate(weeks):
            if (seed_val + i) % 4 == 0:
                events.append({"date": w, "status": 3, "remark": "未到"})
            elif (seed_val + i) % 6 == 0:
                events.append({"date": w, "status": 1, "remark": "迟到"})
            elif (seed_val + i) % 8 == 0:
                events.append({"date": w, "status": 4, "remark": "病假"})
            else:
                events.append({"date": w, "status": 0, "remark": None})
    else:  # D: 缺勤严重
        for i, w in enumerate(weeks):
            if (seed_val + i) % 3 == 0:
                events.append({"date": w, "status": 3, "remark": "未到"})
            elif (seed_val + i) % 5 == 0:
                events.append({"date": w, "status": 1, "remark": "迟到"})
            else:
                events.append({"date": w, "status": 0, "remark": None})
    return events


def _knowledge_mastery_scores(student_id: int, tier: int, scores: list[float]) -> dict[int, float]:
    """为 7 个知识点生成掌握度分数（point_id → score）。"""
    seed_val = sum(int(c) for c in str(student_id) if c.isdigit())
    avg = sum(scores) / len(scores)
    mastery: dict[int, float] = {}

    # 知识点 1-2: 网络体系结构 (module 1)
    # 知识点 3-4: 数据链路层 (module 2)
    # 知识点 5-7: 传输层 (module 3)

    point_base = {
        1: avg + (seed_val % 5) - 2,       # OSI 七层模型
        2: avg + ((seed_val // 3) % 5) - 2,  # TCP/IP 四层模型
        3: avg + ((seed_val // 5) % 7) - 3,  # 以太网帧格式
        4: avg + ((seed_val // 7) % 7) - 3,  # ARP 协议
        5: avg + ((seed_val // 2) % 5) - 2,  # TCP 三次握手
        6: avg + ((seed_val // 4) % 5) - 2,  # TCP 四次挥手
        7: avg + ((seed_val // 6) % 7) - 3,  # UDP 协议特点
    }

    for pid, base in point_base.items():
        score = max(0.0, min(100.0, base))
        mastery[pid] = round(score, 1)

    return mastery


def _attendance_stats(events: list[dict]) -> tuple[float, int]:
    """计算出勤率和缺勤次数。"""
    if not events:
        return 1.0, 0
    weights = {0: 1.0, 1: 0.5, 2: 0.5, 3: 0.0, 4: 0.7}
    total = sum(weights.get(e["status"], 0.0) for e in events)
    absent = sum(1 for e in events if e["status"] == 3)
    return total / len(events), absent


def _gen_tags(tier: int, trend: str, attendance_events: list[dict],
              mastery_scores: dict[int, float]) -> str:
    """根据数据模式生成学情标签。"""
    tags = []
    if tier == 0:
        tags.append("学习积极")
        tags.append("各科均衡")
    elif tier == 1:
        if trend == "up":
            tags.append("稳步提升")
        else:
            tags.append("稳定踏实")
    elif tier == 2:
        if trend == "up":
            tags.append("进步明显")
        elif trend == "down":
            tags.append("成绩下滑")
        else:
            tags.append("中等水平")
    elif tier == 3:
        tags.append("需要关注")
        if trend == "down":
            tags.append("成绩下滑")
    else:
        tags.append("多门课程成绩不理想")
        tags.append("需重点关注")

    # 缺勤标签
    _, absent = _attendance_stats(attendance_events)
    if absent >= 3:
        tags.append("出勤风险")
    elif absent >= 1:
        tags.append("偶尔缺勤")

    return ", ".join(tags)


def _gen_module_strengths(mastery_scores: dict[int, float]) -> tuple[str, str]:
    """聚合知识点掌握度 → 模块优劣势。"""
    # module 1: points 1-2, module 2: points 3-4, module 3: points 5-7
    modules = {
        "网络体系结构": [1, 2],
        "数据链路层": [3, 4],
        "传输层": [5, 6, 7],
    }
    good = []
    weak = []
    for name, pids in modules.items():
        avg = sum(mastery_scores.get(p, 0) for p in pids) / len(pids)
        if avg >= 80:
            good.append(name)
        elif avg < 60:
            weak.append(name)
    return ", ".join(good), ", ".join(weak)


def _gen_warnings(student_id: int, course_id: int, tier: int, trend: str,
                  scores: list[float], attendance_events: list[dict],
                  mastery_scores: dict[int, float]) -> list[dict]:
    """根据数据模式生成预警记录。"""
    warnings: list[dict] = []
    _, absent = _attendance_stats(attendance_events)

    # W1 成绩下滑
    if trend == "down" and len(scores) >= 2:
        drop = scores[0] - scores[-1]
        if drop >= 15:
            level = 2 if drop >= 25 else 1
            warnings.append({
                "warning_type": "成绩下滑",
                "warning_level": level,
                "warning_reason": f"成绩从{scores[0]:.0f}分下滑至{scores[-1]:.0f}分，降幅{drop:.0f}分",
            })

    # W3 缺勤超标
    if absent >= 3:
        warnings.append({
            "warning_type": "缺勤超标",
            "warning_level": 3 if absent >= 4 else 2,
            "warning_reason": f"本学期缺勤{absent}次，出勤率偏低",
        })
    elif absent >= 1:
        warnings.append({
            "warning_type": "缺勤超标",
            "warning_level": 1,
            "warning_reason": f"本学期有{absent}次缺勤，请注意考勤",
        })

    # W5 知识点薄弱
    weak_count = sum(1 for s in mastery_scores.values() if s < 60)
    if weak_count >= 3:
        warnings.append({
            "warning_type": "知识点薄弱堆积",
            "warning_level": 2 if weak_count >= 5 else 1,
            "warning_reason": f"薄弱知识点{weak_count}个，需重点加强",
        })

    return warnings


def inject_analysis_data() -> None:
    """为所有测试学生注入智能分析模块数据。

    注入内容：
      1. ScoreRecord（成绩记录 → 成绩趋势预测用）
      2. AttendanceRecord（考勤记录 → 学情画像/预警用）
      3. KnowledgeMastery（知识点掌握度 → 知识点热力图用）
      4. StudentProfile（学情画像）
      5. StudentEvaluationResult + EvalDimensionScore（学习质量评价）
      6. StudyWarning（异常学情预警）
    """
    print("[inject-analysis] 开始为所有学生注入智能分析数据...")

    with Session(engine) as session:
        # 覆盖所有学生（1-78），包括基础种子学生和测试学生
        all_student_ids = list(range(1, 79))

        # 目标课程：计算机网络 (course_id=1)
        course_id = 1

        # 确认学生存在
        existing_ids = session.exec(
            select(Student.student_id).where(Student.student_id.in_(all_student_ids))
        ).all()
        if not existing_ids:
            print("[inject-analysis] 未找到学生数据，请先运行 seed --reset")
            return

        print(f"  目标学生: {len(existing_ids)} 人")
        print(f"  目标课程: 计算机网络 (course_id={course_id})")

        # ========== 0. 确保所有学生选修了目标课程 ==========
        enrolled_ids = set(session.exec(
            select(CourseStudent.student_id).where(CourseStudent.course_id == course_id)
        ).all())
        missing_enrollment = [sid for sid in existing_ids if sid not in enrolled_ids]
        if missing_enrollment:
            for sid in missing_enrollment:
                session.add(CourseStudent(course_id=course_id, student_id=sid))
            session.commit()
            print(f"  补充选修关系: {len(missing_enrollment)} 人")

        # ========== 1. 检查并清空已有学生分析数据 ==========
        # ScoreRecord
        old_scores = session.exec(
            select(ScoreRecord).where(
                ScoreRecord.student_id.in_(existing_ids),
                ScoreRecord.course_id == course_id,
            )
        ).all()
        for r in old_scores:
            session.delete(r)
        # AttendanceRecord
        old_att = session.exec(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id.in_(existing_ids),
                AttendanceRecord.course_id == course_id,
            )
        ).all()
        for r in old_att:
            session.delete(r)
        # KnowledgeMastery
        old_km = session.exec(
            select(KnowledgeMastery).where(
                KnowledgeMastery.student_id.in_(existing_ids),
                KnowledgeMastery.course_id == course_id,
            )
        ).all()
        for r in old_km:
            session.delete(r)
        # StudentProfile
        old_sp = session.exec(
            select(StudentProfile).where(
                StudentProfile.student_id.in_(existing_ids),
                StudentProfile.course_id == course_id,
            )
        ).all()
        for r in old_sp:
            session.delete(r)
        # StudentEvaluationResult
        old_ev = session.exec(
            select(StudentEvaluationResult).where(
                StudentEvaluationResult.student_id.in_(existing_ids),
                StudentEvaluationResult.course_id == course_id,
            )
        ).all()
        for r in old_ev:
            session.delete(r)
        # StudyWarning
        old_sw = session.exec(
            select(StudyWarning).where(
                StudyWarning.student_id.in_(existing_ids),
                StudyWarning.course_id == course_id,
            )
        ).all()
        for r in old_sw:
            session.delete(r)
        session.commit()
        print("  已清空测试学生的旧分析数据")

        # ========== 2. 注入数据 ==========
        total_scores = 0
        total_attendance = 0
        total_mastery = 0
        total_profiles = 0
        total_evals = 0
        total_warnings = 0

        for sid in existing_ids:
            tier = _student_tier(sid)
            trend = _tier_trend(tier, sid)
            scores = _deterministic_scores(sid, tier, trend)
            att_events = _deterministic_attendance(sid, tier)
            mastery_dict = _knowledge_mastery_scores(sid, tier, scores)

            # --- 2a. ScoreRecord（4条，对应 batch_id 1~4） ---
            for i, score_val in enumerate(scores):
                batch_id = i + 1  # batch 1=平时作业, 2=实验报告, 3=期中, 4=期末
                is_pass = 1 if score_val >= 60 else 0
                session.add(ScoreRecord(
                    course_id=course_id,
                    student_id=sid,
                    batch_id=batch_id,
                    score=score_val,
                    is_pass=is_pass,
                    create_by=2,  # 王建国
                ))
                total_scores += 1

            # --- 2b. AttendanceRecord（6条） ---
            for evt in att_events:
                session.add(AttendanceRecord(
                    course_id=course_id,
                    student_id=sid,
                    attendance_date=evt["date"],
                    status=evt["status"],
                    remark=evt["remark"],
                    create_by=2,
                ))
                total_attendance += 1

            # --- 2c. KnowledgeMastery（覆盖课程全部知识点） ---
            # 获取课程1的全部知识点
            all_course_points = session.exec(
                select(KnowledgePoint.point_id).join(
                    KnowledgeModule, KnowledgePoint.module_id == KnowledgeModule.module_id
                ).where(KnowledgeModule.course_id == course_id)
            ).all()

            avg_score = sum(scores) / len(scores)
            for point_id in all_course_points:
                # 用学生平均成绩 + 知识点ID偏移生成确定性掌握度
                seed_val = sum(int(c) for c in str(sid) if c.isdigit())
                base = avg_score + ((seed_val * point_id) % 15) - 7
                m_score = round(max(0.0, min(100.0, base)), 1)
                level = 3 if m_score >= 80 else (2 if m_score >= 60 else 1)
                session.add(KnowledgeMastery(
                    course_id=course_id,
                    student_id=sid,
                    point_id=point_id,
                    mastery_score=m_score,
                    mastery_level=level,
                ))
                total_mastery += 1

            # --- 2d. StudentProfile ---
            # 计算三维度得分
            avg_score = sum(scores) / len(scores)
            att_rate, absent = _attendance_stats(att_events)
            att_score = att_rate * 100

            # 学业水平：基于平均成绩
            academic = round(avg_score, 1)
            # 学习态度：基于出勤
            attitude = round(att_score * 0.5 + 50.0, 1)  # 出勤权重0.5 + 基础分
            # 学习进步：基于趋势
            if trend == "up":
                progress = round(50.0 + (scores[-1] - scores[0]) * 2, 1)
            elif trend == "down":
                progress = round(50.0 + (scores[-1] - scores[0]) * 2, 1)
            else:
                progress = 50.0 + abs(scores[-1] - scores[0]) * 0.5
            progress = max(10.0, min(100.0, progress))
            total_profile_score = round((academic + attitude + progress) / 3, 1)

            tags = _gen_tags(tier, trend, att_events, mastery_dict)
            good_mods, weak_mods = _gen_module_strengths(mastery_dict)

            session.add(StudentProfile(
                course_id=course_id,
                student_id=sid,
                academic_score=academic,
                attitude_score=round(attitude, 1),
                progress_score=round(progress, 1),
                total_profile_score=total_profile_score,
                study_tags=tags if tags else None,
                good_modules=good_mods if good_mods else None,
                weak_modules=weak_mods if weak_mods else None,
            ))
            total_profiles += 1

            # --- 2e. StudentEvaluationResult + EvalDimensionScore ---
            # 先获取 eval_id
            eval_level = "优" if total_profile_score >= 85 else (
                "良" if total_profile_score >= 75 else (
                    "中" if total_profile_score >= 60 else "差"
                )
            )
            er = StudentEvaluationResult(
                course_id=course_id,
                student_id=sid,
                total_score=total_profile_score,
                eval_level=eval_level,
            )
            session.add(er)
            session.commit()
            session.refresh(er)

            # 维度得分（dimension 1=学业成绩, 2=学习态度）
            session.add(EvalDimensionScore(
                eval_id=er.eval_id,
                dimension_id=1,
                dimension_score=academic,
            ))
            session.add(EvalDimensionScore(
                eval_id=er.eval_id,
                dimension_id=2,
                dimension_score=round(attitude, 1),
            ))
            total_evals += 1

            # --- 2f. StudyWarning ---
            warnings = _gen_warnings(sid, course_id, tier, trend, scores, att_events, mastery_dict)
            for w in warnings:
                session.add(StudyWarning(
                    course_id=course_id,
                    student_id=sid,
                    warning_type=w["warning_type"],
                    warning_level=w["warning_level"],
                    warning_reason=w["warning_reason"],
                    handle_status=0,
                ))
                total_warnings += 1

            # --- 2g. StudentAnswerRecord（答题记录 → 教师视角热力图数据源） ---
            # 为 Task1（Q1-Q5）和 Task3（Q12-Q16）生成答题记录
            # 问题定义: (task_id, question_id, type, correct_answer, wrong_answers_pool)
            _answer_tasks_def = [
                # Task 1: 计算机网络单元测验1
                (1, 1, 1, "C", ["A", "B", "D"]),
                (1, 2, 1, "C", ["A", "B", "D"]),
                (1, 3, 2, '["A","C"]', ['["A"]', '["C"]', '["A","B"]', '["B","C"]']),
                (1, 4, 3, "正确", ["错误"]),
                (1, 5, 3, "错误", ["正确"]),
                # Task 3: 测验1
                (3, 12, 1, "B", ["A", "C", "D"]),
                (3, 13, 2, '["A","B"]', ['["A"]', '["B"]', '["A","B","C"]', '["A","B","D"]']),
                (3, 14, 1, "B", ["A", "C", "D"]),
                (3, 15, 2, '["A","B","C"]', ['["A","B"]', '["A","C"]', '["B","C"]', '["A","B","C","D"]']),
                (3, 16, 1, "B", ["A", "C", "D"]),
            ]

            total_answers = 0
            for sid in existing_ids:
                tier = _student_tier(sid)
                seed_val = sum(int(c) for c in str(sid) if c.isdigit())

                # 不同档位的正确率
                tier_accuracy = {0: 0.85, 1: 0.72, 2: 0.60, 3: 0.42, 4: 0.22}
                acc = tier_accuracy.get(tier, 0.60)

                for task_id, qid, qtype, correct_ans, wrong_pool in _answer_tasks_def:
                    # 确定性判断是否正确
                    is_correct = ((seed_val * (qid + 7) + sid) % 100) < (acc * 100)
                    score = 5 if is_correct else (2 if qtype == 2 and not is_correct else 0)

                    if is_correct:
                        user_ans = correct_ans
                    else:
                        # 从错误选项池中选取
                        idx = (seed_val + qid * 3) % len(wrong_pool)
                        user_ans = wrong_pool[idx]

                    session.add(StudentAnswerRecord(
                        task_id=task_id,
                        question_id=qid,
                        student_id=sid,
                        user_answer=user_ans,
                        score=score,
                        is_correct=1 if is_correct else 0,
                    ))
                    total_answers += 1

        session.commit()

        print(f"\n[inject-analysis] 注入完成！统计：")
        print(f"  ScoreRecord（成绩记录）: {total_scores} 条")
        print(f"  AttendanceRecord（考勤记录）: {total_attendance} 条")
        print(f"  KnowledgeMastery（知识点掌握度）: {total_mastery} 条")
        print(f"  StudentProfile（学情画像）: {total_profiles} 条")
        print(f"  StudentEvaluationResult（评价结果）: {total_evals} 条")
        print(f"  StudyWarning（学情预警）: {total_warnings} 条")
        print(f"  StudentAnswerRecord（答题记录 → 教师热力图数据源）: {total_answers} 条")

        # 打印一些样本数据
        print("\n[inject-analysis] 样本数据预览：")
        # 找一个优秀学生 (tier 0)
        sample_s = next((sid for sid in existing_ids if _student_tier(sid) == 0), existing_ids[0])
        sample_scores_s = _deterministic_scores(sample_s, 0, _tier_trend(0, sample_s))
        student_s = session.get(Student, sample_s)
        print(f"  S档（优秀）- {student_s.real_name if student_s else sample_s}: "
              f"成绩 {sample_scores_s}, trend={_tier_trend(0, sample_s)}")

        sample_d = next((sid for sid in existing_ids if _student_tier(sid) == 4), existing_ids[-1])
        sample_scores_d = _deterministic_scores(sample_d, 4, _tier_trend(4, sample_d))
        student_d = session.get(Student, sample_d)
        print(f"  D档（不及格）- {student_d.real_name if student_d else sample_d}: "
              f"成绩 {sample_scores_d}, trend={_tier_trend(4, sample_d)}")

        # 查看数据库中实际数据
        class_ids = set()
        for sid in existing_ids:
            st = session.get(Student, sid)
            if st:
                class_ids.add(st.class_id)
        print(f"\n  覆盖班级 ID: {sorted(class_ids)} (软件1801=6, 软件1802=7, 软件1803=8)")
        print("  所有数据已就绪，前端可直接展示！")


def main() -> None:
    parser = argparse.ArgumentParser(description="灌入演示数据")
    parser.add_argument("--reset", action="store_true", help="删库重建后再灌入")
    parser.add_argument("--inject-analysis", action="store_true",
                        help="为所有学生注入智能分析数据（学情画像/成绩趋势/知识点/预警）")
    args = parser.parse_args()
    if args.inject_analysis:
        inject_analysis_data()
    elif args.reset:
        reset()
        seed()
    else:
        # 默认行为：如果没有数据则 seed，否则提示
        with Session(engine) as session:
            existing = session.exec(select(SysRole)).first()
        if existing:
            print("数据已存在。使用 --reset 重建，或 --inject-analysis 注入分析数据")
        else:
            seed()


if __name__ == "__main__":
    main()
