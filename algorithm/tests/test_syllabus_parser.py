"""大纲解析器单元测试。"""
from pathlib import Path

import pytest

from src.syllabus_parser import (
    CheckPoint,
    _cn_num_to_int,
    _split_terms,
    parse_assessment,
    parse_course_objectives,
    parse_syllabus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYLLABUS_PATH = REPO_ROOT / "docs" / "参考资料" / "Net教学大纲.docx"

# 没有大纲文件时跳过(非计网环境)
pytestmark = pytest.mark.skipif(
    not SYLLABUS_PATH.exists(),
    reason=f"大纲文件不存在: {SYLLABUS_PATH}",
)


class TestSyllabusParser:
    """解析器核心行为。"""

    def test_parses_five_chapters(self):
        """计网大纲应解析出 5 个章节考核点。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        assert len(cps) == 5
        codes = [cp.code for cp in cps]
        assert codes == ["ch1", "ch2", "ch3", "ch4", "ch5"]

    def test_chapter_titles_intact(self):
        """章节标题保留原文。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        assert "计算机网络概论" in cps[0].chapter
        assert "应用层" in cps[1].chapter
        assert "传输层" in cps[2].chapter
        assert "网络层" in cps[3].chapter
        assert "链路层" in cps[4].chapter

    def test_hours_extracted(self):
        """学时字段正确解析为整数。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        assert cps[0].hours == 6   # 概述 6 学时
        assert cps[1].hours == 8   # 应用层 8 学时
        assert cps[2].hours == 12  # 传输层 12 学时
        assert cps[3].hours == 12  # 网络层 12 学时
        assert cps[4].hours == 10  # 链路层 10 学时

    def test_key_points_populated(self):
        """每章教学重点非空。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        for cp in cps:
            assert len(cp.key_points) > 0, f"{cp.chapter} 教学重点为空"

    def test_kp_terms_contain_core_terms(self):
        """kp_terms 含核心考核术语。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        all_terms = []
        for cp in cps:
            all_terms.extend(cp.kp_terms)
        # 抽查若干大纲明确出现的术语
        for term in ["TCP", "UDP", "IP", "CSMA/CD", "ARP", "DNS", "VLAN", "子网划分"]:
            assert any(term in t for t in all_terms), f"术语 {term} 未出现在 kp_terms"

    def test_checkpoint_to_dict(self):
        """to_dict 返回完整字段。"""
        cps = parse_syllabus(SYLLABUS_PATH)
        d = cps[0].to_dict()
        for key in ["chapter", "code", "objectives", "key_points",
                    "difficulties", "content", "content_keywords",
                    "hours", "kp_terms"]:
            assert key in d

    def test_course_objectives_extracted(self):
        """课程目标 CT1-CT8 抽取。"""
        objs = parse_course_objectives(SYLLABUS_PATH)
        codes = [o["code"] for o in objs]
        for ct in ["CT1", "CT2", "CT3", "CT4", "CT5", "CT6", "CT7", "CT8"]:
            assert ct in codes
        # 分类应是 知识/能力/素养
        categories = {o["category"] for o in objs}
        assert categories <= {"知识", "能力", "素养"}

    def test_assessment_extracted(self):
        """考核方式文本非空。"""
        text = parse_assessment(SYLLABUS_PATH)
        assert text  # 非空
        assert "考核" in text


class TestParserHelpers:
    """纯函数 helper。"""

    def test_cn_num_to_int_single(self):
        assert _cn_num_to_int("一") == 1
        assert _cn_num_to_int("五") == 5
        assert _cn_num_to_int("3") == 3

    def test_cn_num_to_int_compose(self):
        assert _cn_num_to_int("十一") == 11

    def test_split_terms_dedup(self):
        out = _split_terms("TCP；UDP，TCP、IP")
        assert "TCP" in out
        assert out.count("TCP") == 1  # 去重

    def test_split_terms_empty(self):
        assert _split_terms("") == []

    def test_missing_file_returns_empty(self, tmp_path):
        """文件不存在返回空列表,不抛异常。"""
        cps = parse_syllabus(tmp_path / "nonexistent.docx")
        assert cps == []
