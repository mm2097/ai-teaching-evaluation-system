"""小模型验证器单元测试。"""
from src.verifier import VerifyReport, verify_against_syllabus


class TestVerifierAlignment:
    """对齐校验。"""

    def test_pure_syllabus_kps_pass(self):
        """纯大纲知识点输出应 pass,无幻觉。"""
        r = verify_against_syllabus(
            "该生对TCP协议可靠传输和拥塞控制掌握较好,但在IP数据报寻址和子网划分方面薄弱。",
            {"scene": "diagnosis"},
        )
        assert r.flag == "pass"
        assert len(r.aligned_kps) >= 3
        assert r.hallucinated_kps == []
        assert r.confidence > 0.5

    def test_matched_chapters(self):
        """命中的章节 code 正确。"""
        r = verify_against_syllabus(
            "TCP协议可靠传输与拥塞控制,UDP协议格式",
            {"scene": "diagnosis"},
        )
        assert "ch3" in r.matched_chapters  # 传输层

    def test_confidence_with_hallucination_drops(self):
        """有幻觉时置信度被压低。"""
        r_good = verify_against_syllabus("TCP协议可靠传输", {"scene": "diagnosis"})
        r_bad = verify_against_syllabus(
            "该生在量子加密和神经网络方面有进步,TCP协议掌握良好。",
            {"scene": "diagnosis"},
        )
        assert r_bad.confidence < r_good.confidence
        assert r_bad.confidence <= 0.3


class TestVerifierHallucination:
    """幻觉校验。"""

    def test_hard_hallucin_terms_caught(self):
        """跨领域黑词被捕获,flag=warn。"""
        r = verify_against_syllabus(
            "该生在量子加密和神经网络方面有进步。",
            {"scene": "diagnosis"},
        )
        assert "量子" in r.hallucinated_kps
        assert "神经网络" in r.hallucinated_kps
        assert r.flag == "warn"

    def test_quantum_caught(self):
        """量子加密单独出现也被捕获。"""
        r = verify_against_syllabus(
            "学生提到了量子加密技术。",
            {"scene": "diagnosis"},
        )
        assert "量子" in r.hallucinated_kps or "量子加密" in r.hallucinated_kps
        assert r.flag == "warn"

    def test_no_false_positive_on_synonyms(self):
        """同义表述不误判为幻觉(中文)。"""
        r = verify_against_syllabus(
            "学生正确理解了传输层的作用,端口和套接字概念清晰。",
            {"scene": "diagnosis"},
        )
        assert r.hallucinated_kps == []
        assert r.flag == "pass"


class TestVerifierScenes:
    """不同场景的行为。"""

    def test_judge_scene_high_coverage(self):
        """判题场景:题干传输层,评语提到TCP → 高覆盖。"""
        r = verify_against_syllabus(
            "学生正确描述了TCP协议可靠传输原理,但对拥塞控制略有遗漏,给8分。",
            {"scene": "judge", "question_stem": "简述TCP协议的可靠传输与拥塞控制机制"},
        )
        assert r.coverage >= 0.9
        assert r.flag == "pass"

    def test_judge_scene_does_not_require_full_coverage(self):
        """判题场景覆盖阈值=0,单题不要求覆盖多章。"""
        r = verify_against_syllabus(
            "回答正确。",
            {"scene": "judge", "question_stem": "TCP协议"},
        )
        # 即使覆盖低,判题场景不因覆盖 warn
        assert r.flag in ("pass", "warn")  # 无幻觉则 pass

    def test_diagnosis_with_weak_points(self):
        """诊断带 weak_points → 覆盖按薄弱点章节算。"""
        r = verify_against_syllabus(
            "班级在TCP协议可靠传输和拥塞控制方面掌握不足。",
            {"scene": "diagnosis", "weak_points": ["TCP协议可靠传输", "拥塞控制"]},
        )
        assert r.coverage >= 0.9  # 覆盖了 weak_points 对应章节


class TestVerifierRobustness:
    """稳定性:不阻断主流程。"""

    def test_empty_output(self):
        """空输出不报错,低置信。"""
        r = verify_against_syllabus("", {"scene": "diagnosis"})
        assert r.flag in ("pass", "warn", "skipped")
        assert r.confidence == 0.0

    def test_irrelevant_content(self):
        """完全无关内容:无对齐、无幻觉,低置信。"""
        r = verify_against_syllabus(
            "今天天气不错,适合出去玩。",
            {"scene": "diagnosis"},
        )
        assert r.aligned_kps == []
        assert r.hallucinated_kps == []
        assert r.confidence == 0.0

    def test_verify_report_to_dict(self):
        """to_dict 包含全部字段。"""
        r = verify_against_syllabus("TCP协议", {"scene": "diagnosis"})
        d = r.to_dict()
        for key in ["aligned_kps", "hallucinated_kps", "coverage",
                    "confidence", "flag", "notes", "matched_chapters"]:
            assert key in d

    def test_unsupported_course_returns_skipped(self):
        """不支持的 course_id(非1)走无大纲降级,flag=skipped。"""
        r = verify_against_syllabus("TCP协议", {"scene": "diagnosis"}, course_id=999)
        assert r.flag == "skipped"
