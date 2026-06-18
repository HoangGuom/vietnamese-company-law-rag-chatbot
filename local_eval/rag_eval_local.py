"""Guard-aware local evaluator for the Vietnamese company-law RAG chatbot."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from step3_rag_chatbot import (  # noqa: E402
    DEFAULT_QWEN_MODEL,
    DEFAULT_TOP_K,
    FALLBACK_ANSWER,
    call_grounded_ollama,
    has_forbidden_advice,
    has_reasoning_leak,
    format_source,
    guarded_retrieve,
    load_embedding_model,
    load_vectorstore,
    normalize_for_match,
    unsupported_legal_identifiers,
    valid_citation_indexes,
)


DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "id": "cert_conditions",
        "question": "Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_27", "168_2025_nd_cp_dieu_33"],
        "required_terms": ["ngành, nghề", "tên", "hồ sơ", "lệ phí"],
        "severity": "high",
    },
    {
        "id": "prohibited_founders",
        "question": "Ai không được thành lập và quản lý doanh nghiệp tại Việt Nam?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_17"],
        "required_terms": ["cơ quan nhà nước", "cán bộ"],
        "severity": "high",
    },
    {
        "id": "private_enterprise_dossier",
        "question": "Hồ sơ đăng ký doanh nghiệp tư nhân gồm những giấy tờ nào?",
        "expected_accept": True,
        "expected_chunk_ids": ["67_vbhn_vpqh_dieu_19"],
        "required_terms": ["Giấy đề nghị đăng ký doanh nghiệp", "giấy tờ pháp lý"],
        "severity": "medium",
    },
    {
        "id": "household_form_change",
        "question": "Mẫu số 2 Phụ lục II đăng ký thay đổi hộ kinh doanh gồm những mục nào?",
        "expected_accept": True,
        "expected_chunk_ids": [
            "68_2025_tt_btc_phu_luc_ii_mau_02_part_01",
            "68_2025_tt_btc_phu_luc_ii_mau_02_part_02",
        ],
        "required_terms": ["tên hộ kinh doanh", "trụ sở", "ngành, nghề"],
        "severity": "medium",
    },
    {
        "id": "out_of_scope_food",
        "question": "Cách nấu phở?",
        "expected_accept": False,
        "expected_reason": "out_of_scope",
        "severity": "high",
    },
    {
        "id": "out_of_scope_weather",
        "question": "Thời tiết Hà Nội hôm nay thế nào?",
        "expected_accept": False,
        "expected_reason": "out_of_scope",
        "severity": "medium",
    },
    {
        "id": "gibberish",
        "question": "abc xyz alo?",
        "expected_accept": False,
        "severity": "medium",
    },
    {
        "id": "ambiguous",
        "question": "Cái này làm sao?",
        "expected_accept": False,
        "expected_reason": "ambiguous_question",
        "severity": "medium",
    },
    {
        "id": "typo_but_ambiguous",
        "question": "đăg kí doang ngiệp",
        "expected_accept": False,
        "expected_reason": "ambiguous_question",
        "expected_rewrite": "đăng ký doanh nghiệp",
        "severity": "medium",
    },
    {
        "id": "generic_advice",
        "question": "Tôi nên mở công ty gì?",
        "expected_accept": False,
        "expected_reason": "advice_without_legal_fact",
        "severity": "high",
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
        "required_terms": ["không được thành lập"],
        "severity": "high",
    },
    {
        "id": "advice_plus_concrete_fact",
        "question": (
            "Tôi có nên nộp hồ sơ đăng ký doanh nghiệp qua mạng không, "
            "thủ tục trong tài liệu quy định thế nào?"
        ),
        "expected_accept": True,
        "expected_chunk_ids": [
            "67_vbhn_vpqh_dieu_26",
            "168_2025_nd_cp_dieu_38",
            "168_2025_nd_cp_dieu_39",
        ],
        "required_terms": ["qua mạng", "hồ sơ"],
        "forbidden_advice_terms": ["bạn nên", "tôi khuyên", "tốt nhất"],
        "severity": "high",
    },
]

SEVERITY_WEIGHTS = {"high": 1.25, "medium": 1.0, "low": 0.75}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard-aware local RAG evaluator")
    parser.add_argument("--vectorstore", default="vectorstore/legal_vectorstore.json")
    parser.add_argument("--cases", help="Optional JSONL cases file")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--model", default=DEFAULT_QWEN_MODEL)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--out-dir", default="local_eval/reports")
    return parser.parse_args()


def load_cases(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return DEFAULT_CASES
    cases = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def contains(text: str, term: str) -> bool:
    return normalize_for_match(term) in normalize_for_match(text)


def term_score(text: str, terms: list[str]) -> float:
    if not terms:
        return 1.0
    return sum(contains(text, term) for term in terms) / len(terms)


def evaluate_case(
    case: dict[str, Any],
    runtime: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    started = time.perf_counter()
    retrieval = guarded_retrieve(
        case["question"],
        runtime["model"],
        runtime["manifest"]["embedding_model"],
        runtime["documents"],
        runtime["vectors"],
        args.top_k,
    )
    retrieval_ms = (time.perf_counter() - started) * 1000

    expected_accept = bool(case.get("expected_accept", True))
    decision_correct = retrieval.accepted == expected_accept
    reason_correct = (
        retrieval.reason == case["expected_reason"]
        if case.get("expected_reason")
        else True
    )
    rewrite_correct = (
        retrieval.query.retrieval_question == case["expected_rewrite"]
        if case.get("expected_rewrite")
        else True
    )
    chunk_ids = [chunk.chunk_id for chunk in retrieval.chunks]
    expected_chunks = case.get("expected_chunk_ids") or []
    matched_chunks = sorted(set(chunk_ids) & set(expected_chunks))
    retrieval_recall = (
        len(matched_chunks) / len(expected_chunks)
        if expected_accept and expected_chunks
        else 1.0 if decision_correct else 0.0
    )
    first_hit = next(
        (index + 1 for index, chunk_id in enumerate(chunk_ids) if chunk_id in expected_chunks),
        None,
    )
    mrr = 1.0 / first_hit if first_hit else (1.0 if not expected_accept and decision_correct else 0.0)

    answer = ""
    generation_ms = 0.0
    if expected_accept and retrieval.accepted and args.generate:
        generation_started = time.perf_counter()
        answer = call_grounded_ollama(
            case["question"],
            retrieval.chunks,
            args.max_context_chars,
            args.model,
            args.ollama_url,
            args.temperature,
        )
        generation_ms = (time.perf_counter() - generation_started) * 1000
    elif not retrieval.accepted:
        answer = FALLBACK_ANSWER

    fallback_correct = (
        answer == FALLBACK_ANSWER and not retrieval.chunks
        if not expected_accept
        else answer != FALLBACK_ANSWER if args.generate else True
    )
    citations = valid_citation_indexes(answer, len(retrieval.chunks))
    citation_validity = (
        1.0
        if not expected_accept
        else 1.0 if not args.generate else float(bool(citations))
    )
    required_term_score = (
        term_score(answer, case.get("required_terms") or [])
        if args.generate and expected_accept
        else 1.0
    )
    forbidden_advice = [
        term
        for term in case.get("forbidden_advice_terms") or []
        if contains(answer, term)
    ]
    advice_leak = has_forbidden_advice(answer)
    no_advice_score = 0.0 if forbidden_advice or advice_leak else 1.0
    reasoning_leak = has_reasoning_leak(answer)
    concise_final_answer_score = 0.0 if reasoning_leak else 1.0
    unsupported_identifiers = sorted(unsupported_legal_identifiers(answer, retrieval.chunks))
    identifier_grounding_score = 0.0 if unsupported_identifiers else 1.0

    guard_score = (
        float(decision_correct)
        + float(reason_correct)
        + float(rewrite_correct)
        + float(fallback_correct)
    ) / 4
    if expected_accept:
        case_score = (
            0.30 * guard_score
            + 0.35 * retrieval_recall
            + 0.10 * mrr
            + 0.10 * citation_validity
            + 0.10 * required_term_score
            + 0.02 * no_advice_score
            + 0.02 * concise_final_answer_score
            + 0.01 * identifier_grounding_score
        )
    else:
        case_score = guard_score

    return {
        "id": case["id"],
        "question": case["question"],
        "severity": case.get("severity", "medium"),
        "expected_accept": expected_accept,
        "accepted": retrieval.accepted,
        "decision_correct": decision_correct,
        "reason": retrieval.reason,
        "reason_correct": reason_correct,
        "retrieval_question": retrieval.query.retrieval_question,
        "rewrite_correct": rewrite_correct,
        "top_score": retrieval.top_score,
        "top_gap": retrieval.top_gap,
        "retrieved_sources": [format_source(chunk) for chunk in retrieval.chunks],
        "retrieved_chunk_ids": chunk_ids,
        "matched_chunks": matched_chunks,
        "retrieval_recall_at_k": round(retrieval_recall, 4),
        "mrr": round(mrr, 4),
        "fallback_correct": fallback_correct,
        "sources_empty_when_rejected": bool(not retrieval.chunks) if not expected_accept else True,
        "answer_preview": answer[:1000],
        "citation_validity": citation_validity,
        "required_term_score": round(required_term_score, 4),
        "forbidden_advice_terms_found": forbidden_advice,
        "advice_leak": advice_leak,
        "no_advice_score": no_advice_score,
        "reasoning_leak": reasoning_leak,
        "concise_final_answer_score": concise_final_answer_score,
        "unsupported_identifiers": unsupported_identifiers,
        "identifier_grounding_score": identifier_grounding_score,
        "case_score": round(case_score, 4),
        "telemetry": {
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    }


def summarize(results: list[dict[str, Any]], generated: bool) -> dict[str, Any]:
    valid = [result for result in results if result["expected_accept"]]
    rejected = [result for result in results if not result["expected_accept"]]

    def mean(key: str, rows: list[dict[str, Any]] = results) -> float:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float, bool))]
        return round(statistics.mean(values), 4) if values else 0.0

    false_rejections = sum(not row["accepted"] for row in valid)
    false_acceptances = sum(row["accepted"] for row in rejected)
    total_weight = sum(SEVERITY_WEIGHTS.get(row["severity"], 1.0) for row in results) or 1.0
    weighted_score = sum(
        row["case_score"] * SEVERITY_WEIGHTS.get(row["severity"], 1.0)
        for row in results
    ) / total_weight

    return {
        "case_count": len(results),
        "valid_case_count": len(valid),
        "reject_case_count": len(rejected),
        "generated_answers": generated,
        "overall_score": mean("case_score"),
        "severity_weighted_score": round(weighted_score, 4),
        "guard_decision_accuracy": mean("decision_correct"),
        "rejection_accuracy": mean("decision_correct", rejected),
        "false_rejection_rate": round(false_rejections / len(valid), 4) if valid else 0.0,
        "false_acceptance_rate": round(false_acceptances / len(rejected), 4) if rejected else 0.0,
        "fallback_accuracy": mean("fallback_correct", rejected),
        "rewrite_accuracy": mean("rewrite_correct"),
        "rejected_sources_empty_rate": mean("sources_empty_when_rejected", rejected),
        "retrieval_recall_at_k": mean("retrieval_recall_at_k", valid),
        "retrieval_mrr": mean("mrr", valid),
        "citation_validity": mean("citation_validity", valid),
        "required_term_score": mean("required_term_score", valid),
        "no_advice_score": mean("no_advice_score", valid),
        "concise_final_answer_score": mean("concise_final_answer_score", valid),
        "identifier_grounding_score": mean("identifier_grounding_score", valid),
        "retrieval_ms_avg": round(
            statistics.mean(row["telemetry"]["retrieval_ms"] for row in results), 2
        ),
        "total_ms_avg": round(
            statistics.mean(row["telemetry"]["total_ms"] for row in results), 2
        ),
    }


def write_reports(
    results: list[dict[str, Any]],
    summary: dict[str, Any],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rag_eval_report.json").write_text(
        json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "rag_eval_cases.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "expected_accept",
                "accepted",
                "reason",
                "decision_correct",
                "rewrite_correct",
                "fallback_correct",
                "recall_at_k",
                "mrr",
                "citation_validity",
                "case_score",
                "top_source",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result["id"],
                    result["expected_accept"],
                    result["accepted"],
                    result["reason"],
                    result["decision_correct"],
                    result["rewrite_correct"],
                    result["fallback_correct"],
                    result["retrieval_recall_at_k"],
                    result["mrr"],
                    result["citation_validity"],
                    result["case_score"],
                    result["retrieved_sources"][0] if result["retrieved_sources"] else "",
                ]
            )

    lines = ["# Guard-aware RAG Evaluation", "", "## Summary", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in summary.items())
    lines.extend(["", "## Cases", ""])
    for result in results:
        lines.append(
            f"- `{result['id']}` score={result['case_score']} "
            f"accepted={result['accepted']} reason={result['reason']}"
        )
    (out_dir / "rag_eval_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    manifest, documents, vectors = load_vectorstore(PROJECT_ROOT / args.vectorstore)
    model = load_embedding_model(manifest["embedding_model"])
    runtime = {
        "manifest": manifest,
        "documents": documents,
        "vectors": vectors,
        "model": model,
    }
    results = [evaluate_case(case, runtime, args) for case in cases]
    summary = summarize(results, args.generate)
    write_reports(results, summary, PROJECT_ROOT / args.out_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
