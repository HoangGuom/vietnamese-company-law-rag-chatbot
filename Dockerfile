FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Cache HuggingFace model vào trong image, không download lại mỗi lần start
ENV HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY step3_rag_chatbot.py rag_web_app.py ./
COPY vectorstore ./vectorstore

# Pre-download embedding model vào image khi build
# Clone về rồi docker compose up --build là chạy offline hoàn toàn
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

EXPOSE 8000

CMD ["uvicorn", "rag_web_app:app", "--host", "0.0.0.0", "--port", "8000"]
