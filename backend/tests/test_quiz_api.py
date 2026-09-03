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
    KnowledgeMastery,
    Student,
    StudentAnswerRecord,
    SysUser,
    TaskQuestion,
)
from app.models.question import TASK_TYPE_SELF_PRACTICE


def _user(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


def _create_task(session, question_ids: list[int], *, allow_review: int = 1) -> AnswerTask:
    task = AnswerTask(
        course_id=1,
        task_name=f"regression-{datetime.now().timestamp()}",
        deadline=datetime.now() + timedelta(days=1),
        status=1,
        allow_review=allow_review,
        create_by=1,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    for index, question_id in enumerate(question_ids):
        session.add(TaskQuestion(task_id=task.task_id, question_id=question_id, sort_num=index))
    session.commit()
    return task


def _assign_task_to_class(session, task: AnswerTask, class_id: int = 1) -> None:
    session.add(AnswerTaskClass(task_id=task.task_id, class_id=class_id))
    session.commit()

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
    _assign_task_to_class(session, task)

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


def test_student_can_see_submitted_task_and_record_when_review_disabled(session):
    task = _create_task(session, [1], allow_review=0)
    _assign_task_to_class(session, task)
    result = quiz.submit_answers(
        quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=1, answers={"1": "C"}),
        session=session,
        current_user=_user(session, 2),
    )

    tasks = quiz.list_answer_tasks(
        course_id=None,
        teacher_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    serialized = next(item for item in tasks if item["id"] == task.task_id)
    assert serialized["submitted"] is True
    assert serialized["allowReview"] is False
    assert serialized["mySubmissionId"] == result["submissionId"]

    records = quiz.list_answer_records(
        task_id=None,
        student_id=None,
        course_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    record = next(item for item in records if item["assignmentId"] == task.task_id)
    assert record["id"] == result["submissionId"]
    assert record["score"] == result["score"]

def test_student_cannot_open_detail_when_review_disabled(session):
    task = _create_task(session, [1], allow_review=0)
    _assign_task_to_class(session, task)
    result = quiz.submit_answers(
        quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=1, answers={"1": "C"}),
        session=session,
        current_user=_user(session, 2),
    )

    with pytest.raises(HTTPException) as exc:
        quiz.get_answer_record_detail(
            result["submissionId"],
            session=session,
            current_user=_user(session, 2),
        )
    assert exc.value.status_code == 404


def test_submit_rejects_blank_short_answer(session):
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

    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_answers(
            quiz.SubmitAnswersRequest(
                task_id=task.task_id,
                student_id=1,
                answers={str(question.question_id): "   "},
            ),
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 422


def test_submit_rejects_incomplete_answers(session):
    task = _create_task(session, [1, 2])

    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_answers(
            quiz.SubmitAnswersRequest(task_id=task.task_id, student_id=1, answers={"1": "C"}),
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 422
    assert "未作答" in str(exc_info.value.detail)
    assert not session.exec(
        select(StudentAnswerRecord).where(StudentAnswerRecord.task_id == task.task_id)
    ).all()


def test_empty_short_answer_scores_zero_without_ai(session, monkeypatch):
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
    student = session.exec(select(Student).where(Student.student_id == 1)).first()

    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("AI judge should not be called for empty answers")

    monkeypatch.setattr(quiz.httpx, "post", fail_if_called)
    result = quiz._call_ai_judge(
        session,
        question,
        "   ",
        student.student_id,
        task.task_id,
        20.0,
    )
    session.flush()

    assert called["value"] is False
    assert result == {"score": 0.0, "manual_required": False}
    record = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.question_id == question.question_id,
        )
    ).first()
    assert record.score == 0
    assert record.is_correct == 0
    assert record.judge_reason == "未作答"


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


def test_student_cannot_use_teacher_stream_generate(session):
    with pytest.raises(HTTPException) as exc_info:
        quiz.generate_exercises_stream(
            quiz.GenerateExercisesRequest(
                courseId=1,
                knowledgePoints=["红黑树"],
                questionTypes=["single_choice"],
                questionCount=1,
            ),
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 403

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


def test_student_cannot_create_self_practice_through_generic_task_api(session):
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

    with pytest.raises(HTTPException) as exc_info:
        quiz.create_answer_task(
            request,
            session=session,
            current_user=_user(session, 2),
        )

    assert exc_info.value.status_code == 403


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


def test_publish_assignment_requires_target_class(session):
    request = quiz.SaveAnswerTaskRequest(
        title="Missing class",
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

    with pytest.raises(HTTPException) as exc_info:
        quiz.create_answer_task(
            request,
            session=session,
            current_user=_user(session, 1),
        )

    assert exc_info.value.status_code == 422


def test_publish_saved_task_without_class_is_rejected(session):
    task = _create_task(session, [1])

    with pytest.raises(HTTPException) as exc_info:
        quiz.publish_answer_task(
            task.task_id,
            session=session,
            current_user=_user(session, 1),
        )

    assert exc_info.value.status_code == 422


def test_student_cannot_see_assignment_without_target_class(session):
    task = _create_task(session, [1])

    tasks = quiz.list_answer_tasks(
        course_id=1,
        teacher_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    assert task.task_id not in {item["id"] for item in tasks}


def test_student_cannot_see_or_submit_another_class_task(session):
    session.add(
        ClassInfo(
            class_id=2,
            class_name="计科2402",
            college="计算机学院",
            major="计算机科学与技术",
            grade="2024级",
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


def _generated_self_practice() -> dict:
    suffix = str(datetime.now().timestamp())
    return {
        "questions": [
            {
                "id": -1,
                "type": "single_choice",
                "stem": f"自主练习题一-{suffix}",
                "options": [
                    {"key": "A", "text": "正确选项"},
                    {"key": "B", "text": "错误选项"},
                ],
                "answer": "A",
                "explanation": "选择 A",
                "knowledgePoint": "红黑树",
            },
            {
                "id": -2,
                "type": "judge",
                "stem": f"自主练习题二-{suffix}",
                "answer": "true",
                "explanation": "该说法正确",
                "knowledgePoint": "红黑树",
            },
        ],
        "meta": {"model": "test-model", "elapsedMs": 10},
    }


def _create_open_self_practice(session) -> AnswerTask:
    task = _create_task(session, [1])
    task.task_name = f"【自主练习】{datetime.now().timestamp()}"
    task.task_type = TASK_TYPE_SELF_PRACTICE
    task.create_by = 2
    session.add(task)
    session.commit()
    return task


def test_student_self_practice_start_hides_solutions_and_submit_uses_saved_answers(
    session, monkeypatch
):
    generated = _generated_self_practice()
    monkeypatch.setattr(
        quiz,
        "_generate_exercises",
        lambda *args, **kwargs: generated,
    )

    started = quiz.start_self_practice(
        quiz.GenerateExercisesRequest(
            courseId=1,
            knowledgePoints=["红黑树"],
            questionTypes=["single_choice", "judge"],
            questionCount=2,
        ),
        session=session,
        current_user=_user(session, 2),
    )
    assignment = started["assignment"]
    question_ids = [question["id"] for question in assignment["questions"]]

    assert assignment["title"].startswith("【自主练习】")
    assert all(question["answer"] == "" for question in assignment["questions"])
    assert all(question["explanation"] == "" for question in assignment["questions"])
    persisted_questions = [session.get(AiQuestion, question_id) for question_id in question_ids]
    assert [question.correct_answer for question in persisted_questions] == ["A", "true"]

    result = quiz.submit_self_practice(
        quiz.SelfPracticeSubmitRequest(
            taskId=assignment["id"],
            answers={str(question_ids[0]): "A", str(question_ids[1]): "false"},
        ),
        session=session,
        current_user=_user(session, 2),
    )

    task = session.get(AnswerTask, result["taskId"])
    records = session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == result["taskId"],
        )
    ).all()
    assert task.create_by == 2
    assert task.status == 2
    assert result["score"] == 50
    assert result["correctCount"] == 1
    assert len(records) == 2
    assert {record.student_id for record in records} == {1}
    assert {record.question_id for record in records} == set(question_ids)
    assert len(result["questionResults"]) == 2
    assert result["questionResults"][0]["question"]["answer"] == "A"


def test_teacher_cannot_submit_self_practice(session):
    task = _create_open_self_practice(session)
    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_self_practice(
            quiz.SelfPracticeSubmitRequest(taskId=task.task_id, answers={"1": "C"}),
            session=session,
            current_user=_user(session, 1),
        )

    assert exc_info.value.status_code == 403


def test_self_practice_cannot_be_submitted_through_generic_answer_api(session):
    task = _create_open_self_practice(session)

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


def test_student_cannot_submit_another_students_self_practice(session):
    task = _create_open_self_practice(session)
    with pytest.raises(HTTPException) as exc_info:
        quiz.submit_self_practice(
            quiz.SelfPracticeSubmitRequest(taskId=task.task_id, answers={"1": "C"}),
            session=session,
            current_user=_user(session, 3),
        )

    assert exc_info.value.status_code == 403


def test_self_practice_rolls_back_task_when_grading_fails(session, monkeypatch):
    task = _create_open_self_practice(session)

    def fail_grading(*args, **kwargs):
        raise RuntimeError("grading failed")

    monkeypatch.setattr(quiz, "_grade_task_answers", fail_grading)
    with pytest.raises(RuntimeError, match="grading failed"):
        quiz.submit_self_practice(
            quiz.SelfPracticeSubmitRequest(taskId=task.task_id, answers={"1": "C"}),
            session=session,
            current_user=_user(session, 2),
        )

    persisted_task = session.get(AnswerTask, task.task_id)
    assert persisted_task.status == 1
    assert not session.exec(
        select(StudentAnswerRecord).where(
            StudentAnswerRecord.task_id == task.task_id,
            StudentAnswerRecord.student_id == 1,
        )
    ).all()


def test_error_book_returns_only_own_wrong_answers(session):
    """错题本从答题记录 is_correct=0 聚合，只返回学生本人错题。"""
    # 学生1（张三，user_id=2）做错 question_id=2
    task = _create_task(session, [2])
    session.add(StudentAnswerRecord(
        task_id=task.task_id, question_id=2, student_id=1,
        user_answer="A", score=0, is_correct=0,
    ))
    session.commit()

    items = quiz.get_error_book(
        course_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    assert any(it["quizQuestion"]["id"] == 2 for it in items)
    # 每条都带标准答案，供订正
    wrong = next(it for it in items if it["quizQuestion"]["id"] == 2)
    assert wrong["correctAnswer"]  # 有正确答案
    assert wrong["userAnswer"] == "A"


def test_error_book_teacher_forbidden(session):
    """教师访问错题本应被拒绝（仅学生本人可见）。"""
    with pytest.raises(HTTPException) as exc:
        quiz.get_error_book(
            course_id=None,
            session=session,
            current_user=_user(session, 1),  # 教师
        )
    assert exc.value.status_code == 403


def test_error_book_excludes_pending_manual_short_answer(session):
    """待人工批改的简答题（ai_score 为空）不计入错题本。"""
    # question_id=12 是简答题（type=5）
    task = _create_task(session, [12])
    session.add(StudentAnswerRecord(
        task_id=task.task_id, question_id=12, student_id=1,
        user_answer="随便写的", score=0, is_correct=0, ai_score=None,
    ))
    session.commit()

    items = quiz.get_error_book(
        course_id=None,
        session=session,
        current_user=_user(session, 2),
    )
    assert not any(it["quizQuestion"]["id"] == 12 for it in items)


def test_plan_batches_with_types_covers_all_selected_types():
    """默认 2+2+1 难度分布下，判断题和填空题也应有全局配额。"""
    types = ["single_choice", "multi_choice", "judge", "fill_blank"]
    batches = [("easy", 2), ("medium", 2), ("hard", 1)]
    planned = quiz._plan_batches_with_types(batches, types)

    assert len(planned) == 3
    merged: dict[str, int] = {}
    for _, type_map in planned:
        for t, n in type_map.items():
            merged[t] = merged.get(t, 0) + n
    assert merged["judge"] >= 1
    assert merged["fill_blank"] >= 1
    assert sum(merged.values()) == 5


def test_plan_batches_with_types_respects_per_batch_totals():
    types = ["single_choice", "multi_choice", "judge", "fill_blank"]
    batches = [("easy", 2), ("medium", 2), ("hard", 1)]
    planned = quiz._plan_batches_with_types(batches, types)

    assert planned[0] == ("easy", {"single_choice": 1, "multi_choice": 1})
    assert planned[1] == ("medium", {"judge": 1, "fill_blank": 1})
    assert planned[2] == ("hard", {"single_choice": 1})


def test_distribute_question_types_single_batch_unchanged():
    types = ["single_choice", "multi_choice", "judge", "fill_blank"]
    assert quiz._distribute_question_types(5, types) == {
        "single_choice": 2,
        "multi_choice": 1,
        "judge": 1,
        "fill_blank": 1,
    }


# ===== 删除答题任务 =====
# 使用独立内存库（函数级隔离），避免删除操作污染共享种子数据
# （其他测试文件依赖任务 1/2，且本组用例之间存在删除顺序依赖）。

@pytest.fixture
def delete_engine():
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine, Session as SqlSession

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)

    from datetime import datetime as _dt
    from app.models import (
        Course, CourseStudent, KnowledgeMastery, KnowledgeModule, KnowledgePoint,
        Student, SysRole, SysUser, Teacher,
    )

    with SqlSession(eng) as s:
        s.add(SysRole(role_id=1, role_name="教师", role_code="teacher"))
        s.add(SysRole(role_id=2, role_name="学生", role_code="student"))
        s.add(SysUser(user_id=1, username="teacher", password="x", real_name="王老师", role_id=1, status=1))
        s.add(SysUser(user_id=2, username="s1", password="x", real_name="张三", role_id=2, status=1))
        s.add(Teacher(teacher_id=1, teacher_no="T001", real_name="王老师", user_id=1,
                      college="计算机学院"))
        s.add(ClassInfo(class_id=1, class_name="计科2401", college="计算机学院"))
        s.add(Course(course_id=1, course_code="CS101", course_name="数据结构",
                     teacher_id=1, semester="2024-2025-1", college="计算机学院"))
        s.add(Student(student_id=1, student_no="2024001", real_name="张三", class_id=1, user_id=2))
        s.add(Student(student_id=2, student_no="2024002", real_name="李四", class_id=1, user_id=3))
        s.add(Student(student_id=3, student_no="2024003", real_name="王五", class_id=1, user_id=4))
        for sid in (1, 2, 3):
            s.add(CourseStudent(course_id=1, student_id=sid))
        s.add(KnowledgeModule(module_id=1, course_id=1, module_name="树结构"))
        s.add(KnowledgePoint(point_id=1, module_id=1, point_name="二叉树"))
        s.add(KnowledgePoint(point_id=2, module_id=1, point_name="红黑树"))
        # 题库题目：q1/q2 同属知识点1，q3 属知识点2
        s.add(AiQuestion(question_id=1, course_id=1, point_id=1, type=1,
                          content="Q1", correct_answer="A", create_by=1))
        s.add(AiQuestion(question_id=2, course_id=1, point_id=1, type=1,
                          content="Q2", correct_answer="B", create_by=1))
        s.add(AiQuestion(question_id=3, course_id=1, point_id=2, type=1,
                          content="Q3", correct_answer="A", create_by=1))
        s.add(AnswerTask(task_id=100, course_id=1, task_name="待删除练习",
                          deadline=_dt(2025, 1, 1), status=1, create_by=1))
        s.add(AnswerTask(task_id=101, course_id=1, task_name="【自主练习】红黑树",
                          task_type=TASK_TYPE_SELF_PRACTICE,
                          deadline=_dt(2025, 1, 1), status=2, create_by=2))
        s.commit()
        s.add(AnswerTaskClass(task_id=100, class_id=1))
        s.add(TaskQuestion(task_id=100, question_id=1, sort_num=0))
        # 3 名学生对任务 100 的答题记录
        for sid in (1, 2, 3):
            s.add(StudentAnswerRecord(task_id=100, question_id=1, student_id=sid,
                                       user_answer="A", score=10, is_correct=1))
        # 学生 3 在知识点 1 的另一条剩余记录（task_id=0 旧数据）
        s.add(StudentAnswerRecord(task_id=0, question_id=1, student_id=3,
                                   user_answer="B", score=0, is_correct=0))
        # 掌握度持久化行
        for sid in (1, 2, 3):
            s.add(KnowledgeMastery(course_id=1, student_id=sid, point_id=1,
                                    mastery_score=75, mastery_level=2))
        s.add(KnowledgeMastery(course_id=1, student_id=1, point_id=2,
                                mastery_score=60, mastery_level=2))
        s.commit()
    return eng


@pytest.fixture
def delete_session(delete_engine):
    from sqlmodel import Session as SqlSession
    with SqlSession(delete_engine) as s:
        yield s


def _du(session, user_id: int) -> SysUser:
    return session.get(SysUser, user_id)


def test_delete_task_cascades_records_and_links(delete_session):
    """删除任务级联清除任务-题目/班级关联与答题记录，题库题目保留。"""
    result = quiz.delete_answer_task(
        100,
        session=delete_session,
        current_user=_du(delete_session, 1),
    )

    assert "3 条答题记录" in result["message"]
    assert delete_session.get(AnswerTask, 100) is None
    assert not delete_session.exec(
        select(TaskQuestion).where(TaskQuestion.task_id == 100)
    ).all()
    assert not delete_session.exec(
        select(AnswerTaskClass).where(AnswerTaskClass.task_id == 100)
    ).all()
    assert not delete_session.exec(
        select(StudentAnswerRecord).where(StudentAnswerRecord.task_id == 100)
    ).all()
    # 题库题目保留，可被其他任务复用
    assert delete_session.get(AiQuestion, 1) is not None

    # 学生端任务列表与答题记录同步清除
    tasks = quiz.list_answer_tasks(
        course_id=None,
        teacher_id=None,
        session=delete_session,
        current_user=_du(delete_session, 2),
    )
    assert 100 not in {item["id"] for item in tasks}
    records = quiz.list_answer_records(
        task_id=None,
        student_id=None,
        course_id=None,
        session=delete_session,
        current_user=_du(delete_session, 2),
    )
    assert not any(item["assignmentId"] == 100 for item in records)


def test_delete_task_cleans_up_mastery_leftovers(delete_session):
    """删除记录后：无剩余记录的 (学生, 知识点) 清除掌握度行，有剩余的保留并重算。"""
    quiz.delete_answer_task(
        100,
        session=delete_session,
        current_user=_du(delete_session, 1),
    )

    # 学生1/2 知识点1 已无剩余答题记录 → 掌握度行清除
    assert delete_session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.student_id == 1,
            KnowledgeMastery.point_id == 1,
        )
    ).first() is None
    assert delete_session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.student_id == 2,
            KnowledgeMastery.point_id == 1,
        )
    ).first() is None
    # 学生3 知识点1 仍有剩余记录（task_id=0）→ 掌握度行保留并按剩余记录重算（0/1 → 0 分）
    km3 = delete_session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.student_id == 3,
            KnowledgeMastery.point_id == 1,
        )
    ).first()
    assert km3 is not None
    assert km3.mastery_score == 0.0
    # 未受影响的知识点行不动
    km_other = delete_session.exec(
        select(KnowledgeMastery).where(
            KnowledgeMastery.student_id == 1,
            KnowledgeMastery.point_id == 2,
        )
    ).first()
    assert km_other is not None and km_other.mastery_score == 60


def test_delete_task_rejects_student(delete_session):
    with pytest.raises(HTTPException) as exc_info:
        quiz.delete_answer_task(
            100,
            session=delete_session,
            current_user=_du(delete_session, 2),
        )
    assert exc_info.value.status_code == 403
    # 未删除
    assert delete_session.get(AnswerTask, 100) is not None


def test_delete_task_rejects_self_practice(delete_session):
    with pytest.raises(HTTPException) as exc_info:
        quiz.delete_answer_task(
            101,
            session=delete_session,
            current_user=_du(delete_session, 1),
        )
    assert exc_info.value.status_code == 409
    assert delete_session.get(AnswerTask, 101) is not None


def test_delete_missing_task_returns_404(delete_session):
    with pytest.raises(HTTPException) as exc_info:
        quiz.delete_answer_task(
            99999,
            session=delete_session,
            current_user=_du(delete_session, 1),
        )
    assert exc_info.value.status_code == 404
