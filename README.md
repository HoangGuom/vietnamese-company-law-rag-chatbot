# RAG Chatbot Luật Doanh Nghiệp Việt Nam

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

Chatbot hỏi đáp pháp luật doanh nghiệp Việt Nam, sử dụng RAG (Retrieval-Augmented Generation) với **Qwen3** qua Ollama và **sentence-transformers** để embed văn bản luật. Giao diện web đơn giản, triển khai hoàn toàn bằng Docker.

**Dữ liệu pháp luật hiện hành:**
- Luật Doanh nghiệp hợp nhất 2025 (`67/VBHN-VPQH`)
- Luật sửa đổi bổ sung 2025 (`76/2025/QH15`)
- Nghị định đăng ký doanh nghiệp (`168/2025/NĐ-CP`)

---

## 🌟 Features

- 📚 **Vietnamese company-law Q&A** với nguồn trích dẫn từ chunk pháp luật.
- 🧠 **Local RAG pipeline**: crawl/chunk/embed và lưu tại `vectorstore/legal_vectorstore.json`.
- 🔐 **No cloud API key**: Qwen chạy local qua Ollama.
- 💬 **FastAPI web UI** tại `http://localhost:8000`.
- 🧪 **CLI mode** để debug retrieval và hỏi nhanh.
- 📊 **Legal source audit** để theo dõi văn bản active/inactive.
- 🐳 **Docker ready**: CPU mặc định, NVIDIA GPU dùng override riêng.

## 🏗️ Architecture

```text
Browser / API client
        │
        ▼
FastAPI web app
rag_web_app.py
        │ retrieve
        ▼
Local vectorstore
vectorstore/legal_vectorstore.json
        │ context chunks
        ▼
Ollama server
Qwen model
```

Data build pipeline:

```text
selenium_crawler.py
        ↓
legal_chunks.json
        ↓
tt68_forms_ingest.py
        ↓
generate_audit.py
        ↓
step2_build_vectorstore.py
        ↓
vectorstore/legal_vectorstore.json
```

## 🚀 Quick Start

### Docker

```bash
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Docker sẽ build web app, khởi động Ollama, pull `qwen3:4b` nếu chưa có, và dùng vectorstore đã commit sẵn. Mặc định compose chỉ bind port vào `127.0.0.1` để tránh vô tình mở chatbot/model ra mạng ngoài.

### NVIDIA GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### Python Local

Yêu cầu: cài Python và Ollama trên máy, sau đó mở Ollama trước khi chạy lệnh `ollama pull`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen3:4b
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 127.0.0.1 --port 8000
```

## ⚙️ Configuration

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` local, `http://ollama:11434` Docker | Ollama API base URL |
| `QWEN_MODEL` | `qwen3:4b` | Chat model |
| `VECTORSTORE_PATH` | `vectorstore/legal_vectorstore.json` | Vectorstore path |
| `ENABLE_RETRIEVE_ENDPOINT` | `false` | Enable the retrieval-only debug endpoint |

Change model:

```powershell
$env:QWEN_MODEL="qwen3:8b"
ollama pull qwen3:8b
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 127.0.0.1 --port 8000
```

With Docker:

```powershell
$env:QWEN_MODEL="qwen3:8b"
docker compose up --build
```

Với NVIDIA GPU:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

Tên model trong Compose chỉ được chứa chữ, số và các ký tự `._:/-`.
Compose tự pull model nếu chưa có, warm-up Qwen trước khi mở web app và giữ
model trong VRAM 30 phút. Điều này tránh cold start dài ở lượt hỏi đầu tiên.

## 📖 Usage

### Web Chat

Ask questions like:

```text
Ai không được thành lập doanh nghiệp?
Mẫu số 1 Phụ lục I Thông tư 68/2025/TT-BTC gồm những nội dung gì?
Hồ sơ đăng ký thay đổi nội dung đăng ký hộ kinh doanh gồm những mục nào?
```

### CLI Chat

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py
```

Ask one question:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --question "Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?"
```

Retrieve only:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --retrieve-only --question "Mẫu số 2 Phụ lục II đăng ký thay đổi hộ kinh doanh gồm những mục nào?"
```

### Retrieval guard

Trước khi gọi Qwen, ứng dụng kiểm tra câu hỏi và kết quả retrieval ở tầng Python:

- Từ chối câu hỏi ngoài phạm vi, vô nghĩa, quá mơ hồ hoặc chỉ xin lời khuyên chung.
- Sửa một số lỗi gõ phổ biến nhưng không bổ sung ý nghĩa pháp lý mới.
- Loại kết quả có score thấp hoặc top results quá sát nhau khi câu hỏi không có tín hiệu pháp lý rõ.
- Không gọi LLM và không trả source khi retrieval không đạt yêu cầu; câu trả lời cố định là:
  `Không tìm thấy thông tin trong tài liệu được cung cấp.`

Có thể hiệu chỉnh bằng biến môi trường:

```powershell
$env:MIN_RETRIEVAL_SCORE="0.84"
$env:MIN_TOP_GAP="0.008"
$env:MAX_SCORE_DROP="0.08"
```

Chạy test:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Chạy evaluator khớp với pipeline thật:

```powershell
# Guard + retrieval, không cần Ollama
.\.venv\Scripts\python.exe local_eval\rag_eval_local.py

# Full evaluation, gồm cả câu trả lời Qwen
.\.venv\Scripts\python.exe local_eval\rag_eval_local.py --generate
```

Phần generation dùng structured JSON output, kiểm tra citation, lời khuyên,
reasoning bị lộ và định danh pháp lý không xuất hiện trong context trước khi trả lời.

Định nghĩa metric, công thức, trade-off, nguồn học thuật và giới hạn của benchmark:
[`local_eval/README.md`](local_eval/README.md). Bộ regression mặc định có 80 case
trong [`local_eval/cases/rag_eval_cases.jsonl`](local_eval/cases/rag_eval_cases.jsonl).
Các điểm `overall_score` và `severity_weighted_score` là composite metric tùy biến
của dự án, không phải benchmark chuẩn và không đo riêng năng lực của Qwen.

Báo cáo eval JSON/CSV là runtime artifacts và được `.gitignore`; hãy chạy lại evaluator
để tạo số liệu phù hợp với code, model và phần cứng hiện tại thay vì commit snapshot cũ.

## 🔌 API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web UI |
| `/health` | GET | Health check |
| `/api/chat` | POST | Ask chatbot and return answer + sources |
| `/api/retrieve` | POST | Retrieve source snippets; disabled by default |
| `/docs` | GET | Swagger UI; disabled by default |

`question` is limited to 2,000 characters. Source text is truncated and metadata is
filtered before being returned to clients. Set `ENABLE_RETRIEVE_ENDPOINT=true` only
for trusted debugging environments. Set `ENABLE_API_DOCS=true` only when API schema
discovery is intentionally needed.

Example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Ai không được thành lập doanh nghiệp?", "top_k": 5}'
```

## 📚 Legal Data

Active vectorstore hiện có:

| Văn bản | Active chunks | Ghi chú |
|---|---:|---|
| `67/VBHN-VPQH` | 224 | Văn bản hợp nhất Luật Doanh nghiệp 2025 |
| `76/2025/QH15` | 5 | Luật sửa đổi, bổ sung Luật Doanh nghiệp 2025 |
| `168/2025/NĐ-CP` | 133 | Nghị định hiện hành về đăng ký doanh nghiệp |
| `68/2025/TT-BTC` | 53 | Thông tư biểu mẫu đăng ký doanh nghiệp, hộ kinh doanh |

TT68 hiện có `5` chunk điều khoản/danh mục và `48` chunk nội dung chi tiết từ `33` biểu mẫu DOCX. Một số văn bản cũ như `01/2021/NĐ-CP`, `01/2021/TT-BKHĐT`, `02/2023/TT-BKHĐT`, `59/2020/QH14`, `03/2022/QH15` được giữ để đối chiếu lịch sử nhưng không phải nguồn trả lời chính.

## 🧱 Rebuild Data

Vectorstore JSON đã được commit sẵn tại `vectorstore/legal_vectorstore.json`, nên chỉ cần `requirements.txt` để chạy chatbot. Không cần cài Selenium, Edge driver hay `webdriver-manager` nếu bạn chỉ muốn dùng dữ liệu có sẵn.

Chỉ cài thêm dependencies dev khi muốn tự crawl/tải lại tài liệu pháp luật về máy, bổ sung biểu mẫu, đổi chunking hoặc rebuild embedding:

```powershell
pip install -r requirements-dev.txt
```

Lưu ý: `tt68_forms_ingest.py` cần các file DOCX biểu mẫu trong `downloads/tt68_forms_docx/`. Thư mục `downloads/` không được commit lên GitHub, nên nếu clone mới thì cần tải hoặc tạo các file DOCX này trước khi chạy ingest.

```powershell
.\.venv\Scripts\python.exe selenium_crawler.py
.\.venv\Scripts\python.exe tt68_forms_ingest.py
.\.venv\Scripts\python.exe generate_audit.py
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

Sau khi `legal_chunks.json` thay đổi, luôn chạy lại `step2_build_vectorstore.py`.

## 🗂️ Project Structure

```text
vietnamese-company-law-rag-chatbot/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.gpu.yml
├── requirements.txt
├── rag_web_app.py
├── step3_rag_chatbot.py
├── step2_build_vectorstore.py
├── selenium_crawler.py
├── tt68_forms_ingest.py
├── generate_audit.py
├── legal_chunks.json
├── legal_sources_audit.json
└── vectorstore/
    └── legal_vectorstore.json
```

## 🔐 Security Notes

- Repo mặc định không cần OpenAI/Gemini/Anthropic API key.
- `.env`, `.env.*`, `downloads/`, `drivers/`, cache và log runtime đã được ignore.
- Docker compose chỉ publish `8000` và `11434` trên `127.0.0.1`.
- Web UI render source text bằng DOM/text node để tránh HTML injection từ chunk.
- `/api/retrieve` bị tắt mặc định; source snippet bị giới hạn và metadata dùng allowlist.
- API từ chối câu hỏi rỗng/null byte, giới hạn độ dài câu hỏi và kích thước request body.
- Swagger/OpenAPI bị tắt mặc định; response có CSP, anti-framing, no-sniff và no-store headers.
- `/health` không công khai model, embedding hoặc số lượng tài liệu.
- Hệ thống không lưu lịch sử chat và Qwen chạy qua Ollama local; prompt không được chủ động gửi tới API LLM cloud.

Nếu mở dịch vụ ra Internet, vẫn cần đặt reverse proxy có TLS, authentication,
rate limiting, request logging đã loại bỏ dữ liệu nhạy cảm và monitoring. Cấu hình
mặc định phù hợp chạy local/portfolio, chưa phải cấu hình public multi-tenant.

## 🛠️ Troubleshooting

Test Ollama:

```bash
curl http://localhost:11434/api/tags
```

Test web app:

```bash
curl http://localhost:8000/health
```

If answers do not change after updating data:

```powershell
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

Then restart the app.
