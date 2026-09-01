"""知识点失分率聚合测试。"""
from app.api.v1.analysis import get_knowledge_heatmap
from app.models import CourseTestDetail, SysUser


def test_knowledge_heatmap_aggregates_loss_rate_for_class_and_student(session):
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    session.add_all([
        CourseTestDetail(
            score_id=101,
            student_id=1,
            exam_batch_id=3,
            question1_score=20,
            question1_knowledge="二叉树",
            question2_score=10,
            question2_knowledge="红黑树",
            total_score=70,
            create_by=1,
        ),
        CourseTestDetail(
            score_id=102,
            student_id=2,
            exam_batch_id=3,
            question1_score=5,
            question1_knowledge="二叉树",
            question2_score=15,
            question2_knowledge="红黑树",
            total_score=80,
            create_by=1,
        ),
    ])
    session.flush()

    class_result = get_knowledge_heatmap(
        course_id=1,
        class_id=1,
        student_id=None,
        session=session,
        current_user=teacher,
    )
    point_meta = {item["pointName"]: item for item in class_result["pointMeta"]}
    assert class_result["lossRateByKp"][:2] == [12.5, 12.5]
    assert point_meta["二叉树"]["lossRate"] == 12.5
    assert point_meta["红黑树"]["lossRate"] == 12.5

    student_result = get_knowledge_heatmap(
        course_id=1,
        class_id=1,
        student_id=1,
        session=session,
        current_user=teacher,
    )
    details = {item["pointName"]: item for item in student_result["studentDetail"]}
    assert student_result["lossRateByKp"][:2] == [20.0, 10.0]
    assert student_result["classLossRateByKp"][:2] == [12.5, 12.5]
    assert details["二叉树"]["lossRate"] == 20.0
    assert details["二叉树"]["classLossRate"] == 12.5


def test_knowledge_heatmap_loss_rate_is_zero_without_test_details(session):
    teacher = session.get(SysUser, 1)
    assert teacher is not None

    result = get_knowledge_heatmap(
        course_id=1,
        class_id=1,
        student_id=3,
        session=session,
        current_user=teacher,
    )

    assert result["lossRateByKp"] == [0.0, 0.0, 0.0, 0.0]
    assert all(item["lossRate"] == 0.0 for item in result["studentDetail"])
