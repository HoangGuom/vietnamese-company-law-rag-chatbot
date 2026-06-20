import unittest

from local_eval.rag_eval_local import summarize


def make_result(
    *,
    expected_accept: bool,
    accepted: bool,
    total_ms: float,
    retrieval_ms: float = 10.0,
    generation_ms: float = 0.0,
) -> dict:
    return {
        "expected_accept": expected_accept,
        "accepted": accepted,
        "severity": "medium",
        "case_score": 1.0,
        "decision_correct": expected_accept == accepted,
        "fallback_correct": not expected_accept and not accepted,
        "rewrite_correct": True,
        "sources_empty_when_rejected": not accepted,
        "retrieval_hit_at_k": 1.0 if expected_accept else None,
        "retrieval_recall_at_k": 1.0 if expected_accept else None,
        "judged_retrieval_precision_at_k": 1.0 if expected_accept else None,
        "mrr": 1.0 if expected_accept else None,
        "citation_presence": 1.0 if expected_accept else None,
        "citation_precision": 1.0 if expected_accept else None,
        "generation_error": None,
        "response_non_fallback": 1.0 if expected_accept else None,
        "required_term_score": 1.0,
        "no_advice_score": 1.0,
        "no_reasoning_leak_score": 1.0,
        "identifier_grounding_score": 1.0,
        "direct_verdict_compliance": None,
        "telemetry": {
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
            "total_ms": total_ms,
        },
    }


class EvalMetricTests(unittest.TestCase):
    def test_accepted_latency_is_not_diluted_by_fast_rejections(self):
        results = [
            make_result(
                expected_accept=True,
                accepted=True,
                total_ms=1000,
                generation_ms=900,
            ),
            make_result(expected_accept=False, accepted=False, total_ms=5),
        ]
        summary = summarize(results, generated=True)
        self.assertEqual(summary["accepted_total_ms_avg"], 1000.0)
        self.assertEqual(summary["total_ms_avg"], 502.5)

    def test_latency_percentiles_are_reported(self):
        results = [
            make_result(
                expected_accept=True,
                accepted=True,
                total_ms=value,
                retrieval_ms=value / 10,
                generation_ms=value - value / 10,
            )
            for value in (100, 200, 300, 400, 500)
        ]
        summary = summarize(results, generated=True)
        self.assertEqual(summary["accepted_total_ms_p50"], 300.0)
        self.assertEqual(summary["accepted_total_ms_p95"], 480.0)
        self.assertEqual(summary["retrieval_ms_p95"], 48.0)


if __name__ == "__main__":
    unittest.main()
