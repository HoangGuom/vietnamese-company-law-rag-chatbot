import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import rag_web_app
from step3_rag_chatbot import QueryAnalysis, RetrievalResult, RetrievedChunk


class WebSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(rag_web_app.app)

    def test_rejects_question_longer_than_limit(self):
        with self.assertRaises(ValidationError):
            rag_web_app.ChatRequest(question="a" * 2001)

    def test_rejects_blank_and_null_byte_questions(self):
        for question in ("   \n\t ", "Hồ sơ\x00bí mật"):
            with self.subTest(question=repr(question)):
                with self.assertRaises(ValidationError):
                    rag_web_app.ChatRequest(question=question)

    def test_normalizes_question_whitespace(self):
        request = rag_web_app.ChatRequest(
            question="  Hồ sơ\n\tđăng ký   doanh nghiệp gồm gì?  "
        )
        self.assertEqual(
            request.question,
            "Hồ sơ đăng ký doanh nghiệp gồm gì?",
        )

    def test_restricts_generation_temperature(self):
        with self.assertRaises(ValidationError):
            rag_web_app.ChatRequest(question="Hồ sơ doanh nghiệp?", temperature=1.1)

    def test_retrieve_endpoint_is_disabled_by_default(self):
        request = rag_web_app.ChatRequest(question="Hồ sơ đăng ký doanh nghiệp gồm gì?")
        with patch.object(rag_web_app, "ENABLE_RETRIEVE_ENDPOINT", False):
            with self.assertRaises(HTTPException) as caught:
                rag_web_app.api_retrieve(request)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(caught.exception.detail, "Not found")

    def test_sources_are_truncated_and_metadata_is_whitelisted(self):
        chunk = RetrievedChunk(
            rank=1,
            score=0.9,
            chunk_id="chunk-1",
            text="x" * (rag_web_app.MAX_SOURCE_SNIPPET_CHARS + 50),
            metadata={
                "so_hieu": "168/2025/NĐ-CP",
                "source_url": "https://example.test/law",
                "source_file": "private/internal/path.txt",
                "secret": "must-not-leak",
            },
        )
        source = rag_web_app.chunks_to_sources([chunk])[0]
        self.assertEqual(len(source.text), rag_web_app.MAX_SOURCE_SNIPPET_CHARS)
        self.assertEqual(
            source.metadata,
            {
                "so_hieu": "168/2025/NĐ-CP",
                "source_url": "https://example.test/law",
            },
        )

    def test_backend_exception_is_not_disclosed(self):
        request = rag_web_app.ChatRequest(question="Hồ sơ đăng ký doanh nghiệp gồm gì?")
        accepted = RetrievalResult(
            chunks=[],
            query=QueryAnalysis(
                original_question=request.question,
                retrieval_question=request.question,
                should_retrieve=True,
                reason="accepted",
                has_strong_legal_signal=True,
            ),
            accepted=True,
            reason="accepted",
        )
        with (
            patch.dict(
                rag_web_app.state,
                {
                    "embedding_model": object(),
                    "manifest": {"embedding_model": "fake-model"},
                    "documents": [],
                    "vectors": [],
                },
                clear=True,
            ),
            patch.object(rag_web_app, "guarded_retrieve", return_value=accepted),
            patch.object(
                rag_web_app,
                "call_grounded_ollama",
                side_effect=RuntimeError("http://ollama:11434 secret internal detail"),
            ),
        ):
            with self.assertLogs(rag_web_app.logger, level="ERROR") as logs:
                with self.assertRaises(HTTPException) as caught:
                    rag_web_app.api_chat(request)

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(
            caught.exception.detail,
            rag_web_app.BACKEND_UNAVAILABLE_MESSAGE,
        )
        self.assertNotIn("ollama", caught.exception.detail.lower())
        self.assertIn("secret internal detail", "\n".join(logs.output))

    def test_api_docs_are_disabled_by_default(self):
        paths = {route.path for route in rag_web_app.app.routes}
        self.assertNotIn("/docs", paths)
        self.assertNotIn("/openapi.json", paths)

    def test_health_does_not_disclose_model_or_document_count(self):
        with patch.dict(rag_web_app.state, {}, clear=True):
            payload = rag_web_app.health()
        self.assertEqual(payload, {"ok": False})
        self.assertNotIn("qwen_model", payload)
        self.assertNotIn("embedding_model", payload)
        self.assertNotIn("documents", payload)

    def test_security_headers_are_added(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_rejects_oversized_request_body_before_validation(self):
        oversized = "x" * (rag_web_app.MAX_REQUEST_BODY_BYTES + 1)
        response = self.client.post(
            "/api/chat",
            content=oversized,
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"detail": "Request body too large"})

    def test_model_name_is_html_escaped(self):
        with patch.object(
            rag_web_app,
            "QWEN_MODEL",
            '<script>alert("model")</script>',
        ):
            html = rag_web_app.index()
        self.assertNotIn('<script>alert("model")</script>', html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
