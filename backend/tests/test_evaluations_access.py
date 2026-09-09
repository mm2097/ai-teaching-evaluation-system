"""评价查询接口的权限与范围回归测试。

背景：list_evaluations 原先在 course_id 与 student_id 均未传时对全库
StudentEvaluationResult 逐行实时重算（每行跑一次画像+评价引擎），等同
自我 DoS；且学生仅传 course_id 时可拿到全班评价、教师仅传 student_id
时可跨教师查询任意学生。本文件固化修复后的行为：

- 无 course_id / student_id 一律 422
- 学生角色自动收敛为本人（无论传参形式）
- 教师仅传 student_id 时要求该学生选修了自己的课程
- 教师带 course_id 的常规班级查询不受影响
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.api.v1.evaluations import list_evaluation_results, list_evaluations
from app.models import (
    Course,
    CourseStudent,
    Student,
    SysUser,
)


def test_list_evaluations_without_scope_rejected(session: Session):
    """教师不带 course_id/student_id 调用 → 422（原先触发全表重算）。"""
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    with pytest.raises(HTTPException) as exc:
        list_evaluations(
            course_id=None, eval_level=None, student_id=None,
            session=session, current_user=teacher,
        )
    assert exc.value.status_code == 422


def test_list_results_without_scope_rejected(session: Session):
    """教师不带任何参数调 /evaluations/results → 422（原先返回全库快照）。"""
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    with pytest.raises(HTTPException) as exc:
        list_evaluation_results(
            student_id=None, course_id=None, dept_id=None,
            session=session, current_user=teacher,
        )
    assert exc.value.status_code == 422


def test_student_with_course_only_gets_self_only(session: Session):
    """学生仅传 course_id → 自动收敛为本人，只能拿到自己的评价。"""
    s2 = session.get(SysUser, 3)  # 李四 → student_id=2
    assert s2 is not None

    items = list_evaluations(
        course_id=1, eval_level=None, student_id=None,
        session=session, current_user=s2,
    )

    assert items, "应返回本人评价"
    assert {item["studentDbId"] for item in items} == {2}


def test_student_without_params_scoped_to_self(session: Session):
    """学生不带参数 → 返回自己（选课课程）的评价，而非全库。"""
    s1 = session.get(SysUser, 2)  # 张三 → student_id=1
    assert s1 is not None

    items = list_evaluations(
        course_id=None, eval_level=None, student_id=None,
        session=session, current_user=s1,
    )

    assert items, "应返回本人选修课程的评价"
    assert {item["studentDbId"] for item in items} == {1}


def test_student_cannot_read_other_student(session: Session):
    """学生传他人 student_id → 403（既有行为保持）。"""
    s1 = session.get(SysUser, 2)
    assert s1 is not None

    with pytest.raises(HTTPException) as exc:
        list_evaluations(
            course_id=None, eval_level=None, student_id=2,
            session=session, current_user=s1,
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        list_evaluation_results(
            student_id=2, course_id=None, dept_id=None,
            session=session, current_user=s1,
        )
    assert exc.value.status_code == 403


def test_teacher_cross_course_student_rejected(session: Session):
    """教师仅传 student_id 时：该学生未选修自己的课程 → 403。"""
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    # 构造一个只选修教师 99 课程的外班学生，与教师 1 无共同课程
    session.add(SysUser(user_id=5, username="s100", password="x",
                        real_name="外班学生", role_id=2, status=1))
    session.add(Student(student_id=100, student_no="2024100", real_name="外班学生",
                        class_id=1, gender=1, user_id=5))
    session.add(Course(course_id=99, course_name="外校课程", course_code="X99",
                       teacher_id=99, semester="2024-2025-1",
                       college="计算机学院", status=1))
    session.add(CourseStudent(course_id=99, student_id=100))
    session.commit()
    try:
        with pytest.raises(HTTPException) as exc:
            list_evaluations(
                course_id=None, eval_level=None, student_id=100,
                session=session, current_user=teacher,
            )
        assert exc.value.status_code == 403
    finally:
        for row in session.exec(
            select(CourseStudent).where(CourseStudent.course_id == 99)
        ).all():
            session.delete(row)
        for sid in session.exec(
            select(Student).where(Student.student_id == 100)
        ).all():
            session.delete(sid)
        for u in session.exec(
            select(SysUser).where(SysUser.user_id == 5)
        ).all():
            session.delete(u)
        course = session.get(Course, 99)
        if course:
            session.delete(course)
        session.commit()


def test_teacher_with_course_still_gets_class(session: Session):
    """教师带 course_id 的常规班级查询不受影响（回归保护）。"""
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    items = list_evaluations(
        course_id=1, eval_level=None, student_id=None,
        session=session, current_user=teacher,
    )

    assert {item["studentDbId"] for item in items} == {1, 2, 3}
