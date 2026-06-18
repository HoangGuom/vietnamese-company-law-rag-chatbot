import unittest

import numpy as np

from step3_rag_chatbot import (
    analyze_question,
    answer_passes_grounding_checks,
    RetrievedChunk,
    guarded_retrieve,
    has_reasoning_leak,
    has_forbidden_advice,
    rewrite_query,
    valid_citation_indexes,
)


class FakeEmbeddingModel:
    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        return np.array([[1.0, 0.0]], dtype=np.float32)


class QueryGuardTests(unittest.TestCase):
    def test_rejects_out_of_scope_question(self):
        result = analyze_question("Cách nấu phở?")
        self.assertFalse(result.should_retrieve)
        self.assertEqual(result.reason, "out_of_scope")

    def test_rejects_gibberish(self):
        result = analyze_question("abc xyz alo?")
        self.assertFalse(result.should_retrieve)

    def test_rejects_ambiguous_question(self):
        result = analyze_question("Cái này làm sao?")
        self.assertFalse(result.should_retrieve)
        self.assertEqual(result.reason, "ambiguous_question")

    def test_rewrites_common_registration_typos(self):
        self.assertEqual(rewrite_query("đăg kí doang ngiệp"), "đăng ký doanh nghiệp")
        result = analyze_question("đăg kí doang ngiệp")
        self.assertFalse(result.should_retrieve)
        self.assertEqual(result.reason, "ambiguous_question")

    def test_rejects_generic_advice_request(self):
        result = analyze_question("Tôi nên mở công ty gì?")
        self.assertFalse(result.should_retrieve)
        self.assertEqual(result.reason, "advice_without_legal_fact")

    def test_extracts_legal_question_after_small_talk(self):
        result = analyze_question(
            "Hôm nay trời đẹp, tiện thể cho tôi biết ai không được thành lập doanh nghiệp?"
        )
        self.assertTrue(result.should_retrieve)
        self.assertEqual(
            result.retrieval_question,
            "ai không được thành lập doanh nghiệp?",
        )

    def test_accepts_concrete_legal_question(self):
        result = analyze_question(
            "Hồ sơ đăng ký doanh nghiệp tư nhân gồm những giấy tờ nào?"
        )
        self.assertTrue(result.should_retrieve)

    def test_rejects_candidates_below_score_threshold(self):
        documents = [
            {"chunk_id": "a", "noi_dung": "Hồ sơ doanh nghiệp", "metadata": {}},
            {"chunk_id": "b", "noi_dung": "Đăng ký doanh nghiệp", "metadata": {}},
        ]
        vectors = np.array([[0.80, 0.0], [0.79, 0.0]], dtype=np.float32)
        result = guarded_retrieve(
            "Hồ sơ đăng ký doanh nghiệp gồm gì?",
            FakeEmbeddingModel(),
            "fake-model",
            documents,
            vectors,
            top_k=2,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "score_below_threshold")

    def test_rejects_uncertain_close_results_without_strong_signal(self):
        documents = [
            {"chunk_id": "a", "noi_dung": "Hồ sơ pháp lý", "metadata": {}},
            {"chunk_id": "b", "noi_dung": "Hồ sơ đăng ký", "metadata": {}},
        ]
        vectors = np.array([[0.90, 0.0], [0.895, 0.0]], dtype=np.float32)
        result = guarded_retrieve(
            "Hồ sơ gồm những gì?",
            FakeEmbeddingModel(),
            "fake-model",
            documents,
            vectors,
            top_k=2,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "top_results_too_close")

    def test_validates_only_existing_chunk_citations(self):
        self.assertEqual(valid_citation_indexes("Nội dung [1] và [3].", 2), {1})
        self.assertEqual(valid_citation_indexes("Không có citation.", 3), set())

    def test_detects_visible_reasoning(self):
        self.assertTrue(has_reasoning_leak("Okay, let's tackle this question."))
        self.assertFalse(has_reasoning_leak("Doanh nghiệp phải có hồ sơ hợp lệ [1]."))

    def test_detects_forbidden_advice(self):
        self.assertTrue(has_forbidden_advice("Bạn nên nộp hồ sơ qua mạng [1]."))
        self.assertFalse(has_forbidden_advice("Hồ sơ có thể được nộp qua mạng [1]."))

    def test_rejects_unsupported_legal_identifier(self):
        chunks = [
            RetrievedChunk(
                rank=1,
                score=0.9,
                chunk_id="a",
                text="Điều 26. Đăng ký doanh nghiệp qua mạng.",
                metadata={"so_dieu": "Điều 26"},
            )
        ]
        self.assertTrue(
            answer_passes_grounding_checks("Thực hiện theo Điều 26 [1].", chunks)
        )
        self.assertFalse(
            answer_passes_grounding_checks("Thực hiện theo Điều 5 [1].", chunks)
        )


if __name__ == "__main__":
    unittest.main()
