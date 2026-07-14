"""P0/P1 correctness and security regression tests."""
from datetime import datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlmodel import select

from app.api.v1 import analysis, auth, quiz
from app.core import database
from app.core.config import Settings, settings
from app.core.security import hash_password, verify_password
from app.models import (
    AiGenerationLog,
    AiQuestion,
    AnswerTask,
    CourseStudent,
    KnowledgeMastery,
    KnowledgePoint,
    Student,
    StudentAnswerRecord,
    SysUser,
    TaskQuestion,
)
from app.models.question import TASK_TYPE_ASSIGNMENT, TASK_TYPE_SELF_PRACTICE
from app.services.mastery import compute_class_mastery, refresh_student_mastery


def _user(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


def _question(question_type: int, correct_answer: str) -> AiQuestion:
    return AiQuestion(
        course_id=1,
        point_id=1,
        type=question_type,
        content="hardening-test",
        correct_answer=correct_answer,
        create_by=1,
    )


def test_objective_judge_rejects_blank_and_unknown_false_values():
    question = _question(3, "false")

    assert quiz._judge_objective(question, "false") is True
    assert quiz._judge_objective(question, "错误") is True
    assert quiz._judge_objective(question, "") is False
    assert quiz._judge_objective(question, "not-a-boolean") is False


def test_objective_judge_accepts_json_and_legacy_fill_answers():
    json_question = _question(4, '["链表", "linked list"]')
    legacy_question = _question(4, "链表,linked list")

    assert quiz._judge_objective(json_question, " 链表 ") is True
    assert quiz._judge_objective(json_question, "LINKED   LIST") is True
    assert quiz._judge_objective(legacy_question, "linked list") is True
    assert quiz._judge_objective(json_question, "数组") is False


def test_multi_choice_normalizes_json_order_and_separators():
    question = _question(2, '["A", "C"]')

    assert quiz._judge_objective(question, "C,A") is True
    assert quiz._judge_objective(question, "ac") is True
    assert quiz._judge_objective(question, "A") is False


def test_question_bank_uses_json_for_new_fill_answer_lists(session):
    stem = f"fill-answer-json-{datetime.now().timestamp()}"
    question_id = quiz._ensure_question_in_bank(
        session,
        quiz.QuestionItem(
            id=-1,
            type="fill_blank",
            stem=stem,
            answer="链表",
            answerList=["链表", "linked list"],
            knowledgePoint="二叉树",
        ),
        course_id=1,
        creator_id=1,
    )

    question = session.get(AiQuestion, question_id)
    assert question.correct_answer == '["链表", "linked list"]'
    assert quiz._judge_objective(question, "linked list") is True


def test_old_sqlite_answer_tasks_are_migrated(monkeypatch):
    migration_engine = create_engine("sqlite:///:memory:")
    with migration_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE answer_task ("
            "task_id INTEGER PRIMARY KEY, task_name VARCHAR(64) NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO answer_task (task_id, task_name) VALUES "
            "(1, '普通作业'), (2, '【自主练习】历史任务')"
        ))
    monkeypatch.setattr(database, "engine", migration_engine)

    database._migrate_answer_task_type()

    assert "task_type" in {
        column["name"] for column in inspect(migration_engine).get_columns("answer_task")
    }
    with migration_engine.connect() as connection:
        task_types = connection.execute(text(
            "SELECT task_type FROM answer_task ORDER BY task_id"
        )).scalars().all()
    assert task_types == [TASK_TYPE_ASSIGNMENT, TASK_TYPE_SELF_PRACTICE]


def test_self_practice_updates_personal_but_not_class_mastery(session):
    point = KnowledgePoint(module_id=1, point_name=f"隔离测试-{datetime.now().timestamp()}")
    session.add(point)
    session.flush()
    question = AiQuestion(
        course_id=1,
        point_id=point.point_id,
        type=1,
        content=f"mastery-isolation-{datetime.now().timestamp()}",
        correct_answer="A",
        create_by=1,
    )
    session.add(question)
    session.flush()
    assignment = AnswerTask(
        course_id=1,
        task_name="掌握度隔离教师任务",
        task_type=TASK_TYPE_ASSIGNMENT,
        deadline=datetime.now() + timedelta(days=1),
        status=1,
        create_by=1,
    )
    self_practice = AnswerTask(
        course_id=1,
        task_name="【自主练习】掌握度隔离",
        task_type=TASK_TYPE_SELF_PRACTICE,
        deadline=datetime.now() + timedelta(days=1),
        status=2,
        create_by=2,
    )
    session.add_all([assignment, self_practice])
    session.flush()
    session.add_all([
        TaskQuestion(task_id=assignment.task_id, question_id=question.question_id),
        TaskQuestion(task_id=self_practice.task_id, question_id=question.question_id),
        StudentAnswerRecord(
            task_id=assignment.task_id,
            question_id=question.question_id,
            student_id=1,
            user_answer="A",
            score=100,
            is_correct=1,
        ),
        StudentAnswerRecord(
            task_id=self_practice.task_id,
            question_id=question.question_id,
            student_id=1,
            user_answer="B",
            score=0,
            is_correct=0,
        ),
    ])
    refresh_student_mastery(session, student_id=1, course_id=1)
    session.commit()

    personal = session.exec(select(KnowledgeMastery).where(
        KnowledgeMastery.course_id == 1,
        KnowledgeMastery.student_id == 1,
        KnowledgeMastery.point_id == point.point_id,
    )).one()
    class_stat = next(
        item for item in compute_class_mastery(session, course_id=1, class_id=1)
        if item.point_id == point.point_id
    )
    heatmap = analysis.get_knowledge_heatmap(
        course_id=1,
        class_id=None,
        student_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    point_index = heatmap["knowledgePoints"].index(point.point_name)
    heatmap_score = next(row[2] for row in heatmap["data"] if row[:2] == [point_index, 0])

    assert personal.mastery_score == 50
    assert heatmap_score == 50
    assert class_stat.accuracy == 100


def test_class_mastery_honors_class_id(session):
    student = session.get(Student, 3)
    original_class_id = student.class_id
    student.class_id = 2
    session.add(student)
    session.commit()
    point = KnowledgePoint(module_id=1, point_name=f"班级筛选-{datetime.now().timestamp()}")
    session.add(point)
    session.flush()
    question = AiQuestion(
        course_id=1,
        point_id=point.point_id,
        type=1,
        content=f"class-filter-{datetime.now().timestamp()}",
        correct_answer="A",
        create_by=1,
    )
    task = AnswerTask(
        course_id=1,
        task_name="班级筛选教师任务",
        task_type=TASK_TYPE_ASSIGNMENT,
        deadline=datetime.now() + timedelta(days=1),
        status=1,
        create_by=1,
    )
    session.add_all([question, task])
    session.flush()
    session.add_all([
        StudentAnswerRecord(
            task_id=task.task_id,
            question_id=question.question_id,
            student_id=1,
            user_answer="A",
            score=100,
            is_correct=1,
        ),
        StudentAnswerRecord(
            task_id=task.task_id,
            question_id=question.question_id,
            student_id=3,
            user_answer="B",
            score=0,
            is_correct=0,
        ),
    ])
    session.commit()

    try:
        class_one = next(
            item for item in compute_class_mastery(session, 1, class_id=1)
            if item.point_id == point.point_id
        )
        class_two = next(
            item for item in compute_class_mastery(session, 1, class_id=2)
            if item.point_id == point.point_id
        )
        assert class_one.accuracy == 100
        assert class_two.accuracy == 0
    finally:
        student.class_id = original_class_id
        session.add(student)
        session.commit()


def test_legacy_plaintext_password_is_upgraded_on_login(session):
    user = SysUser(
        username=f"legacy-{datetime.now().timestamp()}",
        password="legacy-pass",
        real_name="兼容用户",
        role_id=2,
        status=1,
    )
    session.add(user)
    session.commit()

    response = auth.login(
        auth.LoginRequest(username=user.username, password="legacy-pass"),
        session=session,
    )
    session.refresh(user)

    payload = jwt.decode(response.token, settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == str(user.user_id)
    assert user.password.startswith("scrypt$")
    assert verify_password("legacy-pass", user.password)


def test_password_hash_is_salted_and_production_requires_secret():
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second
    assert verify_password("same-password", first)
    assert not verify_password("wrong-password", first)
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="short", _env_file=None)


def test_student_cannot_use_teacher_generation_endpoint(session):
    with pytest.raises(HTTPException) as exc_info:
        quiz.generate_exercises_proxy(
            quiz.GenerateExercisesRequest(courseId=1, questionCount=1),
            session=session,
            current_user=_user(session, 3),
        )

    assert exc_info.value.status_code == 403


def test_student_ai_quota_and_per_request_limit_are_persistent(session, monkeypatch):
    monkeypatch.setattr(settings, "AI_STUDENT_DAILY_REQUEST_LIMIT", 2)
    monkeypatch.setattr(settings, "AI_STUDENT_MAX_QUESTIONS", 3)
    current_user = _user(session, 4)
    request = quiz.GenerateExercisesRequest(courseId=1, questionCount=1)

    quiz._consume_ai_quota(request, session, current_user, "self_practice")
    quiz._consume_ai_quota(request, session, current_user, "self_practice")
    with pytest.raises(HTTPException) as quota_error:
        quiz._consume_ai_quota(request, session, current_user, "self_practice")
    with pytest.raises(HTTPException) as size_error:
        quiz._consume_ai_quota(
            quiz.GenerateExercisesRequest(courseId=1, questionCount=4),
            session,
            current_user,
            "self_practice",
        )

    usages = session.exec(select(AiGenerationLog).where(
        AiGenerationLog.user_id == current_user.user_id
    )).all()
    assert quota_error.value.status_code == 429
    assert size_error.value.status_code == 422
    assert len(usages) == 2
