import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.vector_store import bm25_rank
from app.services import intent_router
from app.services.intent_router import IntentRouter, keyword_route, parse_llm_decision

CATALOG = [
    {"code": "ET3300", "name": "Kỹ thuật vi xử lý"},
    {"code": "ET3220", "name": "Điện tử số"},
    {"code": "ET4230", "name": "Mạng máy tính"},
]


class FakeGemini:
    def __init__(self, result):
        self.result = result
        self.prompts = []

    def is_configured(self):
        return True

    def generate_json(self, prompt, system_instruction, schema):
        self.prompts.append(prompt)
        return self.result


class KeywordRouteTests(unittest.TestCase):
    def test_huong_dan_is_not_a_recommendation(self):
        decision = keyword_route("Hướng dẫn thủ tục bảo lưu kết quả học tập", [])
        self.assertEqual(decision.intent, intent_router.REGULATION)

    def test_huong_alone_still_recommends_track(self):
        decision = keyword_route("Tư vấn hướng Vi mạch", [])
        self.assertEqual(decision.intent, intent_router.RECOMMENDATION)
        self.assertEqual(decision.track, "IC_DESIGN")

    def test_ic_track_does_not_match_inside_words(self):
        decision = keyword_route("Gợi ý môn kỳ tới, em thích logic", [])
        self.assertIsNone(decision.track)

    def test_personal_progress_beats_regulation_keywords(self):
        decision = keyword_route("Điều kiện tốt nghiệp của em còn thiếu gì?", [])
        self.assertEqual(decision.intent, intent_router.AUDIT)

    def test_explicit_regulation_beats_audit_keywords(self):
        decision = keyword_route("Cách tính CPA theo quy chế như thế nào?", [])
        self.assertEqual(decision.intent, intent_router.REGULATION)

    def test_hoc_lai_is_regulation_not_simulation(self):
        decision = keyword_route("Học lại môn ET3220 thì điểm tính thế nào?", ["ET3220"])
        self.assertEqual(decision.intent, intent_router.REGULATION)

    def test_fail_question_with_course_is_simulation(self):
        decision = keyword_route("Nếu em trượt Điện tử số thì sao?", ["ET3220"])
        self.assertEqual(decision.intent, intent_router.SIMULATION)
        self.assertEqual(decision.course_codes, ["ET3220"])


class LLMRouteTests(unittest.TestCase):
    def test_llm_decision_is_used_and_validated(self):
        gemini = FakeGemini({"intent": "COURSE_ELIGIBILITY_CHECK", "course_codes": ["et 3300", "XX9999"]})
        decision = IntentRouter(gemini=gemini, mode="llm").route("đk vxl?", [], CATALOG)
        self.assertEqual(decision.router, "llm")
        self.assertEqual(decision.intent, intent_router.COURSE_CHECK)
        # Mã ngoài danh mục bị loại, mã viết có khoảng trắng được chuẩn hóa.
        self.assertEqual(decision.course_codes, ["ET3300"])
        self.assertIn("ET3300: Kỹ thuật vi xử lý", gemini.prompts[0])

    def test_regex_detected_codes_are_kept(self):
        gemini = FakeGemini({"intent": "COURSE_ELIGIBILITY_CHECK", "course_codes": ["ET3300"]})
        decision = IntentRouter(gemini=gemini, mode="llm").route("ET3220 và vxl", ["ET3220"], CATALOG)
        self.assertEqual(sorted(decision.course_codes), ["ET3220", "ET3300"])

    def test_invalid_llm_output_falls_back_to_keywords(self):
        for bad in (None, "not json", {"intent": "UNKNOWN"}, {"course_codes": []}):
            gemini = FakeGemini(bad)
            decision = IntentRouter(gemini=gemini, mode="llm").route("Tiến độ học tập của em", [], CATALOG)
            self.assertEqual(decision.router, "keyword")
            self.assertEqual(decision.intent, intent_router.AUDIT)

    def test_course_intent_without_course_falls_back(self):
        gemini = FakeGemini({"intent": "IMPACT_SIMULATION", "course_codes": []})
        decision = IntentRouter(gemini=gemini, mode="llm").route("trượt thì sao", [], CATALOG)
        self.assertEqual(decision.router, "keyword")

    def test_keyword_mode_never_calls_llm(self):
        gemini = FakeGemini({"intent": "DEGREE_AUDIT", "course_codes": []})
        IntentRouter(gemini=gemini, mode="keyword").route("chào", [], CATALOG)
        self.assertEqual(gemini.prompts, [])

    def test_parse_accepts_json_string_and_drops_bad_track(self):
        decision = parse_llm_decision('{"intent": "COURSE_RECOMMENDATION", "course_codes": [], "track": "X"}', [])
        self.assertEqual(decision.intent, intent_router.RECOMMENDATION)
        self.assertIsNone(decision.track)


class BM25Tests(unittest.TestCase):
    def test_ranks_vietnamese_keyword_matches_first(self):
        docs = [
            "Học bổng khuyến khích học tập dành cho sinh viên giỏi",
            "Cảnh cáo học tập mức 1 được đăng ký tối đa 18 tín chỉ",
            "Mạng máy tính 3 tín chỉ",
        ]
        self.assertEqual(bm25_rank("cảnh cáo mức 1", docs)[0], 1)
        self.assertEqual(bm25_rank("xyz", docs), [])


if __name__ == "__main__":
    unittest.main()
