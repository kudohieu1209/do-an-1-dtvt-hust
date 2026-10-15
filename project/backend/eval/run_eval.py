"""Đánh giá bộ định tuyến intent và chất lượng truy xuất RAG.

Chạy từ thư mục project/backend:
    ./venv/bin/python eval/run_eval.py

- Luôn đo luật từ khóa (không cần mạng).
- Nếu có GEMINI_API_KEY: đo thêm bộ định tuyến LLM và truy xuất bằng Gemini embedding.
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.rag.gemini_service import gemini_service  # noqa: E402
from app.rag.vector_store import vector_store  # noqa: E402
from app.services.chatbot_service import chatbot_service  # noqa: E402
from app.services.data_loader import data_loader  # noqa: E402
from app.services.intent_router import IntentRouter, keyword_route  # noqa: E402

EVAL_FILE = Path(__file__).resolve().parent / "eval_set.json"


def check_case(case, decision):
    ok = decision.intent == case["intent"]
    if ok and case.get("codes"):
        ok = set(case["codes"]).issubset(decision.course_codes)
    if ok and case.get("track"):
        ok = decision.track == case["track"]
    return ok


def eval_router(name, route_fn, cases):
    passed = 0
    failures = []
    for case in cases:
        decision = route_fn(case["q"])
        if check_case(case, decision):
            passed += 1
        else:
            failures.append((case, decision))
    hard = [c for c in cases if c.get("note") == "hard"]
    hard_passed = sum(1 for c in hard if c not in [f[0] for f in failures])
    print(f"\n== Router: {name} ==")
    print(f"Độ chính xác: {passed}/{len(cases)} ({100 * passed / len(cases):.0f}%)"
          f" | câu khó: {hard_passed}/{len(hard)}")
    for case, decision in failures:
        print(f"  ✗ {case['q']!r}: kỳ vọng {case['intent']} {case.get('codes', '')} {case.get('track', '')}"
              f" -> {decision.intent} {decision.course_codes} {decision.track or ''}")
    return passed / len(cases)


def eval_retrieval(cases, k=4):
    hits = 0
    print(f"\n== Retrieval hit@{k} (embedding: {vector_store.provider}) ==")
    for case in cases:
        chunks = vector_store.similarity_search(case["q"], k=k)
        hit = any(
            c["metadata"].get("file_name") == case["file"] and case["contains"] in c["text"]
            for c in chunks
        )
        hits += hit
        if not hit:
            print(f"  ✗ {case['q']!r}: không thấy '{case['contains']}' trong {case['file']}")
    print(f"Hit@{k}: {hits}/{len(cases)} ({100 * hits / len(cases):.0f}%)")
    return hits / len(cases)


def main():
    data = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    cases = data["intent_cases"]
    catalog = data_loader.get_all_courses()

    eval_router(
        "keyword",
        lambda q: keyword_route(q, chatbot_service._detect_courses(q)),
        cases,
    )
    if gemini_service.is_configured():
        llm_router = IntentRouter(gemini=gemini_service, mode="llm")
        eval_router(
            f"llm ({gemini_service.model_name})",
            lambda q: llm_router.route(q, chatbot_service._detect_courses(q), catalog),
            cases,
        )
    else:
        print("\n(Bỏ qua router LLM: chưa cấu hình GEMINI_API_KEY)")

    eval_retrieval(data["retrieval_cases"])


if __name__ == "__main__":
    main()
