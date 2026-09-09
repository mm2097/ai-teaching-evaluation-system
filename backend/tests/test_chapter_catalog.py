from app.models import KnowledgeModule
from app.services.chapter_catalog import canonical_chapter


def test_chapter_is_derived_from_knowledge_point_module(session):
    first = session.get(KnowledgeModule, 1)
    second = session.get(KnowledgeModule, 2)
    first.sort_num = 1
    second.sort_num = 2
    session.add_all([first, second])
    session.commit()

    assert canonical_chapter(session, 1, "二叉树", "第一章 另一种名称") == "第一章 树结构"
    assert canonical_chapter(session, 1, "快速排序", "第一章 另一种名称") == "第二章 排序"


def test_chapter_falls_back_to_module_name_in_raw_text(session):
    module = session.get(KnowledgeModule, 1)
    module.sort_num = 3
    session.add(module)
    session.commit()

    assert canonical_chapter(session, 1, "未登记知识点", "第一章 树结构") == "第三章 树结构"

