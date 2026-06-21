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
    requires_direct_verdict,
    starts_with_direct_verdict,
    direct_verdict_has_explanation,
    unsupported_legal_identifiers,
    valid_citation_indexes,
)

DEFAULT_CASES_PATH = PROJECT_ROOT / "local_eval" / "cases" / "rag_eval_cases.jsonl"
SEVERITY_WEIGHTS = {"high": 1.25, "medium": 1.0, "low": 0.75}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard-aware local RAG evaluator")
    parser.add_argument("--vectorstore", default="vectorstore/legal_vectorstore.json")
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_CASES_PATH.relative_to(PROJECT_ROOT)),
        help="JSONL evaluation cases file",
    )
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--model", default=DEFAULT_QWEN_MODEL)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--out-dir", default="local_eval/reports")
    return parser.parse_args()


def load_cases(path: str) -> list[dict[str, Any]]:
    cases = []
    case_path = Path(path)
    if not case_path.is_absolute():
        case_path = PROJECT_ROOT / case_path
    with case_path.open("r", encoding="utf-8") as handle:
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


def all_citation_indexes(answer: str) -> list[int]:
    return [int(index) for index in re.findall(r"\[(\d+)\]", answer or "")]


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
        else None
    )
    retrieval_precision = (
        len(matched_chunks) / len(chunk_ids)
        if expected_accept and expected_chunks and chunk_ids
        else None
    )
    retrieval_hit = (
        float(bool(matched_chunks))
        if expected_accept and expected_chunks
        else None
    )
    first_hit = next(
        (index + 1 for index, chunk_id in enumerate(chunk_ids) if chunk_id in expected_chunks),
        None,
    )
    mrr = (
        1.0 / first_hit
        if first_hit
        else 0.0 if expected_accept and expected_chunks else None
    )

    answer = ""
    generation_ms = 0.0
    generation_error: str | None = None
    if expected_accept and retrieval.accepted and args.generate:
        generation_started = time.perf_counter()
        try:
            answer = call_grounded_ollama(
                case["question"],
                retrieval.chunks,
                args.max_context_chars,
                args.model,
                args.ollama_url,
                args.temperature,
            )
        except Exception as exc:  # Keep the benchmark running and record infrastructure failures.
            generation_error = f"{type(exc).__name__}: {exc}"
            answer = FALLBACK_ANSWER
        generation_ms = (time.perf_counter() - generation_started) * 1000
    elif not retrieval.accepted:
        answer = FALLBACK_ANSWER

    fallback_correct = (
        bool(answer == FALLBACK_ANSWER and not retrieval.chunks)
        if not expected_accept
        else None
    )
    response_non_fallback = (
        float(answer != FALLBACK_ANSWER)
        if args.generate and expected_accept
        else None
    )
    citation_indexes = all_citation_indexes(answer)
    valid_citations = valid_citation_indexes(answer, len(retrieval.chunks))
    citation_presence = (
        float(bool(citation_indexes))
        if args.generate and expected_accept
        else None
    )
    citation_precision = (
        len([index for index in citation_indexes if 1 <= index <= len(retrieval.chunks)])
        / len(citation_indexes)
        if args.generate and expected_accept and citation_indexes
        else 0.0 if args.generate and expected_accept else None
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
    no_reasoning_leak_score = 0.0 if reasoning_leak else 1.0
    unsupported_identifiers = sorted(unsupported_legal_identifiers(answer, retrieval.chunks))
    identifier_grounding_score = 0.0 if unsupported_identifiers else 1.0
    direct_verdict_required = requires_direct_verdict(case["question"])
    direct_verdict_compliance = (
        float(
            starts_with_direct_verdict(answer)
            and direct_verdict_has_explanation(answer)
        )
        if args.generate and expected_accept and direct_verdict_required
        else None
    )

    guard_score = (
        float(decision_correct)
        + float(reason_correct)
        + float(rewrite_correct)
    ) / 3
    if expected_accept:
        case_score = (
            0.30 * guard_score
            + 0.30 * (retrieval_recall if retrieval_recall is not None else 1.0)
            + 0.10 * (mrr if mrr is not None else 1.0)
            + 0.05 * (citation_presence if citation_presence is not None else 1.0)
            + 0.05 * (citation_precision if citation_precision is not None else 1.0)
            + 0.10 * required_term_score
            + 0.02 * no_advice_score
            + 0.02 * no_reasoning_leak_score
            + 0.01 * identifier_grounding_score
            + 0.05 * (
                direct_verdict_compliance
                if direct_verdict_compliance is not None
                else 1.0
            )
        )
    else:
        case_score = (
            float(decision_correct)
            + float(reason_correct)
            + float(rewrite_correct)
            + float(bool(fallback_correct))
            + float(not retrieval.chunks)
        ) / 5

    return {
        "id": case["id"],
        "category": case.get("category", "uncategorized"),
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
        "retrieval_hit_at_k": retrieval_hit,
        "retrieval_recall_at_k": (
            round(retrieval_recall, 4) if retrieval_recall is not None else None
        ),
        "judged_retrieval_precision_at_k": (
            round(retrieval_precision, 4) if retrieval_precision is not None else None
        ),
        "mrr": round(mrr, 4) if mrr is not None else None,
        "fallback_correct": fallback_correct,
        "response_non_fallback": response_non_fallback,
        "sources_empty_when_rejected": bool(not retrieval.chunks) if not expected_accept else True,
        "answer_preview": answer[:1000],
        "generation_error": generation_error,
        "citation_indexes": citation_indexes,
        "invalid_citation_indexes": sorted(
            {index for index in citation_indexes if index not in valid_citations}
        ),
        "citation_presence": citation_presence,
        "citation_precision": (
            round(citation_precision, 4) if citation_precision is not None else None
        ),
        "required_term_score": round(required_term_score, 4),
        "forbidden_advice_terms_found": forbidden_advice,
        "advice_leak": advice_leak,
        "no_advice_score": no_advice_score,
        "reasoning_leak": reasoning_leak,
        "no_reasoning_leak_score": no_reasoning_leak_score,
        "unsupported_identifiers": unsupported_identifiers,
        "identifier_grounding_score": identifier_grounding_score,
        "direct_verdict_required": direct_verdict_required,
        "direct_verdict_compliance": direct_verdict_compliance,
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

    def mean(key: str, rows: list[dict[str, Any]] = results) -> float | None:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float, bool))]
        return round(statistics.mean(values), 4) if values else None

    def telemetry_values(key: str, rows: list[dict[str, Any]]) -> list[float]:
        return [
            float(row["telemetry"][key])
            for row in rows
            if isinstance(row.get("telemetry", {}).get(key), (int, float))
        ]

    def percentile(values: list[float], fraction: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        weight = position - lower
        return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)

    false_rejections = sum(not row["accepted"] for row in valid)
    false_acceptances = sum(row["accepted"] for row in rejected)
    true_acceptances = sum(row["accepted"] for row in valid)
    true_rejections = sum(not row["accepted"] for row in rejected)
    accepted_count = sum(row["accepted"] for row in results)
    guard_precision = (
        true_acceptances / accepted_count if accepted_count else 0.0
    )
    guard_recall = true_acceptances / len(valid) if valid else 0.0
    guard_f1 = (
        2 * guard_precision * guard_recall / (guard_precision + guard_recall)
        if guard_precision + guard_recall
        else 0.0
    )
    guard_specificity = true_rejections / len(rejected) if rejected else 0.0
    total_weight = sum(SEVERITY_WEIGHTS.get(row["severity"], 1.0) for row in results) or 1.0
    weighted_score = sum(
        row["case_score"] * SEVERITY_WEIGHTS.get(row["severity"], 1.0)
        for row in results
    ) / total_weight

    retrieval_times = telemetry_values("retrieval_ms", results)
    accepted_total_times = telemetry_values(
        "total_ms",
        [row for row in valid if row["accepted"]],
    )
    generation_times = telemetry_values(
        "generation_ms",
        [row for row in valid if row["accepted"]],
    )

    return {
        "case_count": len(results),
        "valid_case_count": len(valid),
        "reject_case_count": len(rejected),
        "generated_answers": generated,
        "overall_score": mean("case_score"),
        "severity_weighted_score": round(weighted_score, 4),
        "guard_decision_accuracy": mean("decision_correct"),
        "guard_precision": round(guard_precision, 4),
        "guard_recall": round(guard_recall, 4),
        "guard_f1": round(guard_f1, 4),
        "guard_specificity": round(guard_specificity, 4),
        "answer_coverage": round(accepted_count / len(results), 4) if results else 0.0,
        "selective_risk": (
            round(false_acceptances / accepted_count, 4) if accepted_count else 0.0
        ),
        "rejection_accuracy": mean("decision_correct", rejected),
        "false_rejection_rate": round(false_rejections / len(valid), 4) if valid else 0.0,
        "false_acceptance_rate": round(false_acceptances / len(rejected), 4) if rejected else 0.0,
        "fallback_accuracy": mean("fallback_correct", rejected),
        "rewrite_accuracy": mean("rewrite_correct"),
        "rejected_sources_empty_rate": mean("sources_empty_when_rejected", rejected),
        "retrieval_hit_rate_at_k": mean("retrieval_hit_at_k", valid),
        "retrieval_recall_at_k": mean("retrieval_recall_at_k", valid),
        "judged_retrieval_precision_at_k": mean(
            "judged_retrieval_precision_at_k", valid
        ),
        "retrieval_mrr": mean("mrr", valid),
        "citation_presence_rate": mean("citation_presence", valid),
        "citation_precision": mean("citation_precision", valid),
        "generation_success_rate": (
            round(
                sum(not row["generation_error"] for row in valid) / len(valid),
                4,
            )
            if generated and valid
            else None
        ),
        "response_non_fallback_rate": mean("response_non_fallback", valid),
        "required_term_score": mean("required_term_score", valid),
        "no_advice_score": mean("no_advice_score", valid),
        "no_reasoning_leak_score": mean("no_reasoning_leak_score", valid),
        "identifier_grounding_score": mean("identifier_grounding_score", valid),
        "direct_verdict_compliance": mean("direct_verdict_compliance", valid),
        "retrieval_ms_avg": round(statistics.mean(retrieval_times), 2),
        "retrieval_ms_p50": percentile(retrieval_times, 0.50),
        "retrieval_ms_p95": percentile(retrieval_times, 0.95),
        "generation_ms_avg": (
            round(statistics.mean(generation_times), 2)
            if generated and generation_times
            else None
        ),
        "generation_ms_p50": (
            percentile(generation_times, 0.50) if generated else None
        ),
        "generation_ms_p95": (
            percentile(generation_times, 0.95) if generated else None
        ),
        "accepted_total_ms_avg": round(statistics.mean(accepted_total_times), 2),
        "accepted_total_ms_p50": percentile(accepted_total_times, 0.50),
        "accepted_total_ms_p95": percentile(accepted_total_times, 0.95),
        "total_ms_avg": round(
            statistics.mean(telemetry_values("total_ms", results)), 2
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
                "response_non_fallback",
                "hit_at_k",
                "recall_at_k",
                "judged_precision_at_k",
                "mrr",
                "citation_presence",
                "citation_precision",
                "required_term_score",
                "direct_verdict_compliance",
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
                    result["response_non_fallback"],
                    result["retrieval_hit_at_k"],
                    result["retrieval_recall_at_k"],
                    result["judged_retrieval_precision_at_k"],
                    result["mrr"],
                    result["citation_presence"],
                    result["citation_precision"],
                    result["required_term_score"],
                    result["direct_verdict_compliance"],
                    result["case_score"],
                    result["retrieved_sources"][0] if result["retrieved_sources"] else "",
                ]
            )

    lines = [
        "# Guard-aware RAG Evaluation",
        "",
        "> Metric definitions, formulas, interpretation and research references: "
        "[`local_eval/README.md`](../README.md).",
        "",
        "> Important: `overall_score` and `severity_weighted_score` are project-specific "
        "composites, not published benchmark metrics. A score of 1.0 only means all "
        "annotated cases in this local test set passed.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary.items())
    lines.extend(["", "## Cases", ""])
    for result in results:
        failed = result["case_score"] < 1.0
        lines.append(
            f"- `{result['id']}` score={result['case_score']} "
            f"accepted={result['accepted']} reason={result['reason']}"
            + (" **REVIEW**" if failed else "")
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
