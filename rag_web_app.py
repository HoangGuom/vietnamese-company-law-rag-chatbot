"""Web app for the Vietnamese company-law RAG chatbot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from step3_rag_chatbot import (
    DEFAULT_TOP_K,
    build_messages,
    call_ollama,
    format_source,
    load_embedding_model,
    load_vectorstore,
    retrieve,
)


VECTORSTORE_PATH = Path(os.getenv("VECTORSTORE_PATH", "vectorstore/legal_vectorstore.json"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3:4b")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=12)
    temperature: float = Field(default=0.2, ge=0, le=2)


class Source(BaseModel):
    rank: int
    score: float
    chunk_id: str
    source: str
    text: str
    metadata: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


app = FastAPI(title="RAG Chatbot Luat Doanh Nghiep")
state: dict[str, Any] = {}


@app.on_event("startup")
def startup() -> None:
    manifest, documents, vectors = load_vectorstore(VECTORSTORE_PATH)
    embedding_model = load_embedding_model(manifest["embedding_model"])
    state.update(
        {
            "manifest": manifest,
            "documents": documents,
            "vectors": vectors,
            "embedding_model": embedding_model,
        }
    )


def retrieve_sources(request: ChatRequest) -> list[Source]:
    chunks = retrieve(
        request.question,
        state["embedding_model"],
        state["manifest"]["embedding_model"],
        state["documents"],
        state["vectors"],
        request.top_k,
    )
    return chunks_to_sources(chunks)


def chunks_to_sources(chunks: list[Any]) -> list[Source]:
    return [
        Source(
            rank=chunk.rank,
            score=chunk.score,
            chunk_id=chunk.chunk_id,
            source=format_source(chunk),
            text=chunk.text,
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RAG Chatbot Luật Doanh Nghiệp</title>
  <style>
    :root { color-scheme: light; font-family: Arial, sans-serif; }
    body { margin: 0; background: #eef2f6; color: #1f2933; }
    main { max-width: 1040px; margin: 0 auto; padding: 28px 18px 42px; }
    header { display: flex; justify-content: space-between; gap: 12px; align-items: end; margin-bottom: 18px; }
    h1 { font-size: 26px; margin: 0; }
    .meta { color: #52606d; font-size: 14px; }
    .panel { background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }
    textarea { width: 100%; min-height: 130px; resize: vertical; box-sizing: border-box; font: inherit; padding: 12px; border: 1px solid #c7ced9; border-radius: 6px; line-height: 1.5; }
    .row { display: flex; gap: 10px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
    button { border: 0; background: #0f766e; color: white; border-radius: 6px; padding: 10px 16px; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .65; cursor: wait; }
    input { width: 62px; padding: 8px; border: 1px solid #c7ced9; border-radius: 6px; }
    .status { color: #52606d; font-size: 14px; }
    .grid { display: grid; grid-template-columns: 1.35fr .9fr; gap: 16px; margin-top: 16px; }
    #answer { white-space: pre-wrap; line-height: 1.6; margin-top: 12px; }
    .source { border: 1px solid #e3e7ee; border-radius: 8px; padding: 12px; margin-top: 10px; }
    .source b { color: #0f766e; display: block; margin-bottom: 4px; }
    .score { color: #6b7280; font-size: 13px; }
    .snippet { color: #4b5563; margin-top: 8px; line-height: 1.45; font-size: 14px; }
    @media (max-width: 820px) { header { display: block; } .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>RAG Chatbot Luật Doanh Nghiệp</h1>
      <div class="meta">Truy xuất văn bản luật, trả lời bằng Qwen và hiển thị nguồn trích dẫn.</div>
    </div>
    <div class="meta">Model: qwen3:4b</div>
  </header>
  <section class="panel">
    <textarea id="question" placeholder="Nhập câu hỏi về luật doanh nghiệp...">Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?</textarea>
    <div class="row">
      <button id="ask">Hỏi chatbot</button>
      <label>Top K <input id="topK" type="number" min="1" max="12" value="5"></label>
      <span id="status" class="status"></span>
    </div>
  </section>
  <div id="result" class="grid" style="display:none;">
    <section class="panel">
      <h2 style="font-size:18px; margin:0;">Trả lời</h2>
      <div id="answer"></div>
    </section>
    <section class="panel">
      <h2 style="font-size:18px; margin:0;">Nguồn truy xuất</h2>
      <div id="sources"></div>
    </section>
  </div>
</main>
<script>
const ask = document.getElementById('ask');
const question = document.getElementById('question');
const topK = document.getElementById('topK');
const result = document.getElementById('result');
const answer = document.getElementById('answer');
const sources = document.getElementById('sources');
const status = document.getElementById('status');

ask.onclick = async () => {
  ask.disabled = true;
  status.textContent = 'Đang truy xuất tài liệu và gọi Qwen...';
  answer.textContent = '';
  sources.innerHTML = '';
  result.style.display = 'block';
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: question.value, top_k: Number(topK.value)})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    answer.textContent = data.answer;
    for (const src of data.sources) {
      const item = document.createElement('div');
      item.className = 'source';

      const sourceTitle = document.createElement('b');
      sourceTitle.textContent = src.source;

      const score = document.createElement('div');
      score.className = 'score';
      score.textContent = `score=${src.score.toFixed(4)} · chunk_id=${src.chunk_id}`;

      const snippet = document.createElement('div');
      snippet.className = 'snippet';
      snippet.textContent = src.text.slice(0, 900).replaceAll('\\n', ' ');

      item.append(sourceTitle, score, snippet);
      sources.appendChild(item);
    }
  } catch (err) {
    answer.textContent = String(err.message || err);
  } finally {
    ask.disabled = false;
    status.textContent = '';
  }
};
</script>
</body>
</html>
"""


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "documents": len(state.get("documents", [])),
        "embedding_model": state.get("manifest", {}).get("embedding_model"),
        "qwen_model": QWEN_MODEL,
    }


@app.post("/api/retrieve")
def api_retrieve(request: ChatRequest) -> dict[str, list[Source]]:
    return {"sources": retrieve_sources(request)}


@app.post("/api/chat", response_model=ChatResponse)
def api_chat(request: ChatRequest) -> ChatResponse:
    chunks = retrieve(
        request.question,
        state["embedding_model"],
        state["manifest"]["embedding_model"],
        state["documents"],
        state["vectors"],
        request.top_k,
    )
    sources = chunks_to_sources(chunks)
    messages = build_messages(request.question, chunks, MAX_CONTEXT_CHARS)
    try:
        answer = call_ollama(messages, QWEN_MODEL, OLLAMA_URL, request.temperature)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot call Qwen via Ollama: {exc}") from exc
    return ChatResponse(answer=answer, sources=sources)
