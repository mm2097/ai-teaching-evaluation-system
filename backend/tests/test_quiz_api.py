"""Regression tests for quiz task serialization and scoring."""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.api.v1 import quiz
from app.models import (
    AiQuestion,
    AnswerTask,
    AnswerTaskClass,
    ClassInfo,
    StudentAnswerRecord,
    SysUser,
    TaskQuestion,
)


def _user(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


def _create_task(session, question_ids: list[int]) -> AnswerTask:
    task = AnswerTask(
        course_id=1,
        task_name=f"regression-{datetime.now().timestamp()}",
        deadline=datetime.now() + timedelta(days=1),
        status=1,
        create_by=1,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    for index, question_id in enumerate(question_ids):
        session.add(TaskQuestion(task_id=task.task_id, question_id=question_id, sort_num=index))
    session.commit()
    return task


def test_task_list_restores_stored_choice_options(session):
    task = _create_task(session, [1])

    tasks = quiz.list_answer_tasks(
        course_id=1,
        teacher_id=None,
        session=session,
        current_user=_user(session, 1),
    )
    serialized = next(item for item in tasks if item["id"] == task.task_id)

    assert serialized["questions"][0]["options"][0] == {
        "key": "A",
        "text": "每个节点是红色或黑色",
    }


def test_student_task_list_does_not_expose_solutions(session):
    task = _create_task(session, [1])

    tasks = quiz.list_answer_tasks(
        course_id=1,
        teacher_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    serialized = next(item for item in tasks if item["id"] == task.task_id)

    assert serialized["questions"][0]["answer"] == ""
    assert serialized["questions"][0]["explanation"] == ""


def test_resubmission_replaces_previous_answer_records(session):
    task = _create_task(session, [1])

    first = quiz.submit_answers(
        quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=2, answers={"1": "C"}),
        session=session,
        current_user=_user(session, 2),
    )
    second = quiz.submit_answers(
        quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=2, answers={"1": "A"}),
        session=session,
        current_user=_user(session, 2),
    )

    records = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == 1,
        )
    ).all()
    assert first["score"] == 100
    assert second["score"] == 0
    assert len(records) == 1
    assert not session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == 2,
        )
    ).all()


def test_answer_record_detail_uses_real_submission_id(session):
    task = _create_task(session, [1])
    result = quiz.submit_answers(
        quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=1, answers={"1": "C"}),
        session=session,
        current_user=_user(session, 2),
    )

    detail = quiz.get_answer_record_detail(
        result["submissionId"],
        session=session,
        current_user=_user(session, 2),
    )

    assert result["submissionId"] > 0
    assert result["questionResults"][0]["question"]["answer"] == "C"
    assert detail["score"] == 100
    assert detail["questionResults"][0]["userAnswer"] == "C"
    assert detail["questionResults"][0]["isCorrect"] is True


def test_short_answer_persists_scaled_score(session, monkeypatch):
    question = AiQuestion(
        course_id=1,
        point_id=1,
        type=5,
        content="Explain the traversal strategy.",
        correct_answer="Reference answer",
        create_by=1,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    task = _create_task(session, [question.question_id])

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"total_score": 8, "reason": "mostly correct", "flag": "normal"}

    monkeypatch.setattr(quiz.httpx, "post", lambda *args, **kwargs: FakeResponse())
    result = quiz.submit_answers(
        quiz.SubmitAnswersRequest(
            task_id=task.task_id,
            student_id=1,
            answers={str(question.question_id): "My answer"},
        ),
        session=session,
        current_user=_user(session, 2),
    )
    record = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.question_id == question.question_id,
        )
    ).one()

    assert result["score"] == 80
    assert record.score == 80
    assert record.ai_score == 8


def test_short_answer_manual_fallback_is_not_reported_as_wrong(session, monkeypatch):
    question = AiQuestion(
        course_id=1,
        point_id=1,
        type=5,
        content="Explain why the traversal is stable.",
        correct_answer="Reference answer",
        create_by=1,
    )
    session.add(question)
    session.commit()
    session.refresh(question)
    task = _create_task(session, [question.question_id])

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "total_score": None,
                "reason": "AI service is not configured",
                "flag": "manual_required",
            }

    monkeypatch.setattr(quiz.httpx, "post", lambda *args, **kwargs: FakeResponse())
    result = quiz.submit_answers(
        quiz.SubmitAnswersRequest(
            task_id=task.task_id,
            student_id=1,
            answers={str(question.question_id): "My answer"},
        ),
        session=session,
        current_user=_user(session, 2),
    )
    detail = quiz.get_answer_record_detail(
        result["submissionId"],
        session=session,
        current_user=_user(session, 2),
    )

    assert result["score"] == 0
    assert result["manualRequiredCount"] == 1
    assert result["manualQuestionIds"] == [question.question_id]
    assert detail["questionResults"][0]["isCorrect"] is False
    assert detail["questionResults"][0]["manualRequired"] is True


def test_student_cannot_create_teacher_assignment(session):
    request = quiz.SaveAnswerTaskRequest(
        title="Teacher assignment",
        courseId=1,
        status="published",
    )

    with pytest.raises(HTTPException) as exc_info:
        quiz.create_answer_task(
            request,
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 403


def test_student_self_practice_uses_authenticated_creator(session):
    request = quiz.SaveAnswerTaskRequest(
        title="【自主练习】红黑树",
        courseId=1,
        status="published",
        questions=[
            quiz.QuestionItem(
                id=1,
                stem="红黑树的性质不包括以下哪项？",
                answer="C",
            )
        ],
    )

    result = quiz.create_answer_task(
        request,
        session=session,
        current_user=_user(session, 2),
    )
    task = session.get(AnswerTask, result["id"])

    assert task.create_by == 2
    assert task.status == 1


def test_teacher_assignment_persists_target_class(session):
    request = quiz.SaveAnswerTaskRequest(
        title="Class assignment",
        courseId=1,
        classId=1,
        className="计科2401",
        questions=[
            quiz.QuestionItem(
                id=1,
                stem="红黑树的性质不包括以下哪项？",
                answer="C",
            )
        ],
    )

    result = quiz.create_answer_task(
        request,
        session=session,
        current_user=_user(session, 1),
    )
    link = session.exec(
        select(AnswerTaskClass).where(AnswerTaskClass.task_id == result["id"])
    ).one()

    assert result["classId"] == 1
    assert link.class_id == 1


def test_student_cannot_see_or_submit_another_class_task(session):
    session.add(
        ClassInfo(
            class_id=2,
            class_name="计科2402",
            college="计算机学院",
            enroll_year=2024,
        )
    )
    session.commit()
    task = _create_task(session, [1])
    session.add(AnswerTaskClass(task_id=task.task_id, class_id=2))
    session.commit()

    tasks = quiz.list_answer_tasks(
        course_id=1,
        teacher_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    assert task.task_id not in {item["id"] for item in tasks}

    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_answers(
            quiz.SubmitAnswersRequest(
                task_id=task.task_id,
                student_id=1,
                answers={"1": "C"},
            ),
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 403


def test_student_cannot_publish_teacher_task(session):
    task = _create_task(session, [1])

    with pytest.raises(HTTPException) as exc_info:
        quiz.publish_answer_task(
            task.task_id,
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 403


def test_student_cannot_submit_closed_task(session):
    task = _create_task(session, [1])
    task.status = 2
    session.add(task)
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_answers(
            quiz.SubmitAnswersRequest(
                task_id=task.task_id,
                student_id=1,
                answers={"1": "C"},
            ),
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 409
