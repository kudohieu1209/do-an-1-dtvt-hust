"""Bộ định tuyến intent cho Hybrid Agent.

Hai tầng:
1. ``LLM``: Gemini đọc câu hỏi (kèm lịch sử ngắn và danh mục học phần của
   CTĐT đang hoạt động) rồi trả về JSON có cấu trúc: intent, mã học phần,
   định hướng chuyên sâu. Nhờ đó hiểu được cách nói tự nhiên, từ lóng và câu
   follow-up ("môn này thì sao?") mà không cần bảng từ khóa.
2. ``Keyword``: bộ luật từ khóa xác định, dùng khi chưa cấu hình Gemini, khi
   gọi API lỗi hoặc khi LLM trả về kết quả không hợp lệ.

LLM chỉ quyết định *gọi công cụ nào*; mọi phép tính (điều kiện học phần,
CPA, tín chỉ) vẫn do Rule Engine thực hiện nên kết quả luôn xác định.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from app.core.config import INTENT_ROUTER_MODE

SIMULATION = "IMPACT_SIMULATION"
RECOMMENDATION = "COURSE_RECOMMENDATION"
SYLLABUS = "RAG_SYLLABUS"
REGULATION = "RAG_REGULATION"
AUDIT = "DEGREE_AUDIT"
COURSE_CHECK = "COURSE_ELIGIBILITY_CHECK"
GREETING = "GENERAL_GREETING"
GENERAL = "RAG_GENERAL"

INTENTS = (SIMULATION, RECOMMENDATION, SYLLABUS, REGULATION, AUDIT, COURSE_CHECK, GREETING, GENERAL)
TRACKS = ("IC_DESIGN", "EMBEDDED_IOT", "TELECOM_NETWORK", "BIOMEDICAL")


@dataclass
class RouteDecision:
    intent: str
    course_codes: List[str] = field(default_factory=list)
    track: Optional[str] = None
    router: str = "keyword"


def _has_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


SIMULATION_KEYWORDS = ("trượt", "tạch", "rớt", "không qua", "ảnh hưởng")
# "hướng" đứng riêng là tín hiệu chọn chuyên ngành, nhưng "hướng dẫn" thì không.
RECOMMEND_PATTERN = re.compile(
    r"nên học|nên đăng ký|gợi ý|tư vấn môn|kỳ tới|kỳ sau|kỳ 7|kỳ 8|chọn môn|hướng(?!\s*dẫn)"
)
SYLLABUS_KEYWORDS = (
    "nội dung", "học gì", "học những gì", "đề cương", "phần mềm",
    "công cụ", "tool", "thực hành gì", "kiến thức", "giáo trình",
    "tài liệu", "dạy gì", "làm gì", "mô tả môn",
)
REGULATION_KEYWORDS = (
    "quy chế", "quy định", "tối thiểu", "tối đa", "bao nhiêu tín chỉ", "giới hạn tín chỉ",
    "học bổng", "cảnh cáo", "buộc thôi học", "rút học phần", "điểm w", "thủ tục",
    "chuẩn ngoại ngữ", "chuẩn tiếng anh", "toeic", "ielts", "vstep", "học phí",
    "bảo lưu", "chính sách", "nhận đồ án", "làm đồ án tốt nghiệp", "xét tốt nghiệp",
    "điều kiện tốt nghiệp", "cải thiện điểm", "học lại", "thang điểm", "cách tính",
)
REGULATION_ARTICLE = re.compile(r"\bđiều\s+\d+\b")
# Câu hỏi về văn bản quy chế luôn đi RAG, kể cả khi có nhắc CPA ("cách tính CPA").
EXPLICIT_REGULATION_KEYWORDS = ("quy chế", "quy định", "cách tính", "thang điểm")
AUDIT_KEYWORDS = (
    "tiến độ", "còn thiếu", "tích lũy", "cpa", "gpa", "bảng điểm", "bằng khá",
    "bằng giỏi", "nợ môn", "kéo điểm",
)
COURSE_QUESTION_KEYWORDS = (
    "điều kiện", "học được không", "được không", "đăng ký được", "cùng lúc",
    "đồng thời", "tiên quyết", "song hành", "môn",
)
GREETINGS = ("chào", "chào bạn", "hello", "hi", "alo", "menu", "help", "bạn là ai")


def detect_track(msg_lower: str) -> Optional[str]:
    if re.search(r"vi mạch|bán dẫn|\bic\b|vlsi", msg_lower):
        return "IC_DESIGN"
    if re.search(r"nhúng|embedded|\biot\b", msg_lower):
        return "EMBEDDED_IOT"
    if re.search(r"viễn thông|telecom|\b5g\b|truyền thông", msg_lower):
        return "TELECOM_NETWORK"
    if re.search(r"y sinh|biomedical", msg_lower):
        return "BIOMEDICAL"
    return None


def keyword_route(message: str, detected_codes: List[str]) -> RouteDecision:
    """Phân loại bằng luật từ khóa (không cần mạng)."""
    msg_lower = message.lower()
    codes = list(detected_codes)

    def decide(intent: str, track: Optional[str] = None) -> RouteDecision:
        return RouteDecision(intent=intent, course_codes=codes, track=track, router="keyword")

    if codes and _has_any(msg_lower, SIMULATION_KEYWORDS):
        return decide(SIMULATION)

    if RECOMMEND_PATTERN.search(msg_lower):
        return decide(RECOMMENDATION, detect_track(msg_lower))

    if _has_any(msg_lower, SYLLABUS_KEYWORDS):
        return decide(SYLLABUS)

    explicit_regulation = _has_any(msg_lower, EXPLICIT_REGULATION_KEYWORDS) or REGULATION_ARTICLE.search(msg_lower)
    if not explicit_regulation and _has_any(msg_lower, AUDIT_KEYWORDS):
        return decide(AUDIT)

    if explicit_regulation or _has_any(msg_lower, REGULATION_KEYWORDS):
        return decide(REGULATION)

    has_raw_code = re.search(r"\b[A-Z]{2,3}\s*\d{4}[A-Z]?\b", message.upper())
    if codes and (_has_any(msg_lower, COURSE_QUESTION_KEYWORDS) or len(codes) >= 2 or has_raw_code):
        return decide(COURSE_CHECK)

    if msg_lower.strip() in GREETINGS:
        return decide(GREETING)

    return decide(GENERAL)


ROUTER_INSTRUCTION = """Bạn là bộ phân loại câu hỏi cho trợ lý học tập ĐHBK Hà Nội. Chỉ trả về JSON.

Chọn đúng một intent:
- IMPACT_SIMULATION: sinh viên hỏi hậu quả nếu trượt/không qua một môn cụ thể.
- COURSE_RECOMMENDATION: xin gợi ý chọn môn kỳ tới hoặc định hướng chuyên sâu.
- RAG_SYLLABUS: hỏi nội dung, đề cương, công cụ, kiến thức của một môn.
- RAG_REGULATION: hỏi quy chế/quy định chung: tín chỉ tối thiểu/tối đa, cảnh cáo, học bổng, học phí, chuẩn ngoại ngữ, thủ tục, cách tính điểm, học lại/cải thiện theo quy chế.
- DEGREE_AUDIT: hỏi về tình hình cá nhân: tiến độ, tín chỉ đã tích lũy, CPA của mình, còn thiếu gì để tốt nghiệp, cách kéo CPA của mình.
- COURSE_ELIGIBILITY_CHECK: hỏi điều kiện đăng ký/tiên quyết/học trước/song hành của môn cụ thể, hoặc có học được môn đó (cùng lúc) không.
- GENERAL_GREETING: chào hỏi, hỏi bot làm được gì.
- RAG_GENERAL: câu hỏi khác về CTĐT/trường.

course_codes: mã học phần (trong danh mục bên dưới) mà câu hỏi nhắc tới, kể cả qua tên gọi tắt
(vd "vxl" = Kỹ thuật vi xử lý, "dts" = Điện tử số) hoặc qua ngữ cảnh hội thoại ("môn này").
Không bịa mã ngoài danh mục. track: IC_DESIGN | EMBEDDED_IOT | TELECOM_NETWORK | BIOMEDICAL hoặc null.
"""

ROUTER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {"type": "STRING", "enum": list(INTENTS)},
        "course_codes": {"type": "ARRAY", "items": {"type": "STRING"}},
        "track": {"type": "STRING", "enum": list(TRACKS), "nullable": True},
    },
    "required": ["intent", "course_codes"],
}


def parse_llm_decision(raw: Any, known_codes: Iterable[str]) -> Optional[RouteDecision]:
    """Kiểm tra đầu ra của LLM; trả về None nếu không hợp lệ."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw, dict) or raw.get("intent") not in INTENTS:
        return None
    known = set(known_codes)
    codes: List[str] = []
    for code in raw.get("course_codes") or []:
        normalized = re.sub(r"\s+", "", str(code)).upper()
        if normalized in known and normalized not in codes:
            codes.append(normalized)
    track = raw.get("track") if raw.get("track") in TRACKS else None
    return RouteDecision(intent=raw["intent"], course_codes=codes, track=track, router="llm")


class IntentRouter:
    def __init__(self, gemini=None, mode: str = INTENT_ROUTER_MODE):
        self.gemini = gemini
        self.mode = mode

    def _llm_enabled(self) -> bool:
        return self.mode in ("auto", "llm") and self.gemini is not None and self.gemini.is_configured()

    def route(
        self,
        message: str,
        detected_codes: List[str],
        course_catalog: List[Dict[str, Any]],
        history: Optional[List[Dict[str, str]]] = None,
    ) -> RouteDecision:
        fallback = keyword_route(message, detected_codes)
        if not self._llm_enabled():
            return fallback

        catalog_text = "\n".join(f"{c['code']}: {c['name']}" for c in course_catalog)
        history_text = ""
        if history:
            lines = []
            for item in history[-4:]:
                role = "Sinh viên" if item.get("role") == "user" else "Trợ lý"
                content = (item.get("content") or "").strip()
                if content:
                    lines.append(f"{role}: {content[:300]}")
            history_text = "\n".join(lines)

        prompt = (
            f"### DANH MỤC HỌC PHẦN\n{catalog_text}\n\n"
            f"### LỊCH SỬ GẦN ĐÂY\n{history_text or '(trống)'}\n\n"
            f"### CÂU HỎI\n{message}"
        )
        raw = self.gemini.generate_json(prompt, ROUTER_INSTRUCTION, ROUTER_SCHEMA)
        known = {c["code"] for c in course_catalog} | set(detected_codes)
        decision = parse_llm_decision(raw, known)
        if decision is None:
            return fallback

        # Mã môn mà regex/alias bắt được là chắc chắn, luôn giữ lại.
        for code in detected_codes:
            if code not in decision.course_codes:
                decision.course_codes.append(code)
        # Các intent cần môn học mà không có môn nào thì để luật từ khóa quyết định.
        if decision.intent in (SIMULATION, COURSE_CHECK) and not decision.course_codes:
            return fallback
        return decision
