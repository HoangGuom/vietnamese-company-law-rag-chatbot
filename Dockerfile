FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip==26.1.2 \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY vectorstore ./vectorstore

# Pre-download embedding model vào image khi build
# Sau này chạy offline hoàn toàn, không cần HuggingFace internet lúc runtime
RUN python - <<'PYEOF'
from sentence_transformers import SentenceTransformer
import json, pathlib

vs_path = pathlib.Path("vectorstore/legal_vectorstore.json")
manifest = json.loads(vs_path.read_text(encoding="utf-8"))["manifest"]
model_name = manifest["embedding_model"]
print(f"Pre-downloading embedding model: {model_name}")
SentenceTransformer(model_name)
print("Done.")
PYEOF

COPY step3_rag_chatbot.py rag_web_app.py ./

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "rag_web_app:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "8", "--timeout-keep-alive", "5"]
