"""Run an end-to-end semantic smoke test against the local vectorstore/Ollama."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from step3_rag_chatbot import (
    FALLBACK_ANSWER,
    call_grounded_ollama,
    guarded_retrieve,
    load_embedding_model,
    load_vectorstore,
)


CASES = [
    {
        "id": "cert_conditions",
        "question": "Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_27"],
    },
    {
        "id": "prohibited_founders",
        "question": "Ai không được thành lập và quản lý doanh nghiệp tại Việt Nam?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_17"],
    },
    {
        "id": "private_enterprise_dossier",
        "question": "Hồ sơ đăng ký doanh nghiệp tư nhân gồm những giấy tờ nào?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_19"],
    },
    {
        "id": "household_form_change",
        "question": "Mẫu số 2 Phụ lục II đăng ký thay đổi hộ kinh doanh gồm những mục nào?",
        "expected_accept": True,
        "expected_chunk_ids": ["68_2025_tt_btc_phu_luc_ii_mau_02_part_01"],
    },
    {
        "id": "out_of_scope_food",
        "question": "Cách nấu phở?",
        "expected_accept": False,
    },
    {
        "id": "out_of_scope_weather",
        "question": "Thời tiết Hà Nội hôm nay thế nào?",
        "expected_accept": False,
    },
    {
        "id": "gibberish",
        "question": "abc xyz alo?",
        "expected_accept": False,
    },
    {
        "id": "ambiguous",
        "question": "Cái này làm sao?",
        "expected_accept": False,
    },
    {
        "id": "typo_but_ambiguous",
        "question": "đăg kí doang ngiệp",
        "expected_accept": False,
        "expected_rewrite": "đăng ký doanh nghiệp",
    },
    {
        "id": "generic_advice",
        "question": "Tôi nên mở công ty gì?",
        "expected_accept": False,
    },
    {
        "id": "small_talk_plus_legal",
        "question": (
            "Hôm nay trời đẹp, tiện thể cho tôi biết ai không được "
            "thành lập doanh nghiệp?"
        ),
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_17"],
        "expected_rewrite": "ai không được thành lập doanh nghiệp?",
    },
    {
        "id": "advice_plus_concrete_fact",
        "question": (
            "Tôi có nên nộp hồ sơ đăng ký doanh nghiệp qua mạng không, "
            "thủ tục trong tài liệu quy định thế nào?"
        ),
        "expected_accept": True,
    },
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    manifest, documents, vectors = load_vectorstore(
        ROOT / "vectorstore" / "legal_vectorstore.json"
    )
    model = load_embedding_model(manifest["embedding_model"])
    results = []

    for case in CASES:
        started = time.perf_counter()
        retrieval = guarded_retrieve(
            case["question"],
            model,
            manifest["embedding_model"],
            documents,
            vectors,
            top_k=5,
        )
        if retrieval.accepted:
            answer = call_grounded_ollama(
                case["question"],
                retrieval.chunks,
                12000,
                "qwen3:4b",
                "http://localhost:11434",
                0.0,
            )
        else:
            answer = FALLBACK_ANSWER

        chunk_ids = [chunk.chunk_id for chunk in retrieval.chunks]
        expected_chunks = case.get("expected_chunk_ids") or []
        result = {
            "id": case["id"],
            "question": case["question"],
            "expected_accept": case["expected_accept"],
            "accepted": retrieval.accepted,
            "decision_correct": retrieval.accepted == case["expected_accept"],
            "reason": retrieval.reason,
            "rewrite": retrieval.query.retrieval_question,
            "rewrite_correct": (
                retrieval.query.retrieval_question == case["expected_rewrite"]
                if case.get("expected_rewrite")
                else True
            ),
            "top_score": retrieval.top_score,
            "top_gap": retrieval.top_gap,
            "chunk_ids": chunk_ids,
            "expected_chunk_hit": (
                any(chunk_id in chunk_ids for chunk_id in expected_chunks)
                if expected_chunks
                else True
            ),
            "answer": answer,
            "fallback_exact": answer == FALLBACK_ANSWER,
            "citation_present": bool(
                retrieval.accepted
                and any(f"[{index}]" in answer for index in range(1, len(chunk_ids) + 1))
            ),
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    report_path = ROOT / "local_eval" / "reports" / "chatbot_semantic_test.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
