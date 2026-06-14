# ⚖️ Vietnamese Company Law RAG Chatbot

Chatbot tra cứu pháp luật doanh nghiệp Việt Nam bằng RAG (Retrieval-Augmented Generation), sử dụng Qwen qua Ollama, embedding đa ngôn ngữ và vectorstore local.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Web%20API-green)
![Ollama](https://img.shields.io/badge/Ollama-Qwen-black)
![Docker](https://img.shields.io/badge/Docker-supported-blue)

## 🌟 Features

- 📚 **Tra cứu luật doanh nghiệp tiếng Việt** với nguồn trích dẫn rõ ràng.
- 🧠 **RAG local**: dữ liệu pháp luật được chunk, embed và lưu trong `vectorstore/legal_vectorstore.json`.
- 🐳 **Chạy bằng Docker hoặc Python local** trên máy mới.
- 🔐 **Không cần API key cloud**: Qwen chạy local qua Ollama.
- 💬 **Web UI local** tại `http://localhost:8000`.
- 🧪 **CLI debug retrieval** và test câu hỏi nhanh.
- 📊 **Audit dữ liệu** để biết văn bản nào đang active/inactive.
- 🧾 **Pipeline ingest biểu mẫu DOCX** của `68/2025/TT-BTC`.
- ⚙️ **CPU-safe by default**; GPU NVIDIA dùng file override riêng.

## 🏗️ Architecture

```text
┌──────────────────────┐
│  Browser / API client │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ FastAPI web app       │
│ rag_web_app.py        │
└──────────┬───────────┘
           │ retrieve
           ▼
┌──────────────────────┐
│ Local vectorstore     │
│ legal_vectorstore.json│
└──────────┬───────────┘
           │ context chunks
           ▼
┌──────────────────────┐
│ Ollama server         │
│ Qwen model            │
└──────────────────────┘
```

Data build pipeline:

```text
selenium_crawler.py
        ↓
legal_chunks.json
        ↓
tt68_forms_ingest.py
        ↓
Generate audit.py
        ↓
step2_build_vectorstore.py
        ↓
vectorstore/legal_vectorstore.json
```

## 🔧 Core Components

| File | Vai trò |
|---|---|
| `selenium_crawler.py` | Crawl văn bản luật dạng HTML/web |
| `tt68_forms_ingest.py` | Đọc DOCX biểu mẫu TT68 và thêm chunk chi tiết |
| `Generate audit.py` | Tạo báo cáo tổng quan từ `legal_chunks.json` |
| `step2_build_vectorstore.py` | Build embedding/vectorstore |
| `step3_rag_chatbot.py` | Chat RAG qua terminal, debug retrieval |
| `rag_web_app.py` | FastAPI web app và API chatbot |
| `docker-compose.yml` | Chạy Ollama + web app bằng Docker CPU-safe |
| `docker-compose.gpu.yml` | Override để dùng NVIDIA GPU |

## 🚀 Quick Start With Docker

Docker là cách dễ nhất để chạy sản phẩm trên máy mới.

Prerequisites:

- Docker Desktop đã cài và đang chạy.
- Lần đầu cần internet để build image, tải embedding model và pull Qwen.

```bash
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
docker compose up --build
```

Mở trình duyệt:

```text
http://localhost:8000
```

Docker compose mặc định chỉ bind web app và Ollama vào `127.0.0.1` để tránh vô tình mở chatbot/model ra mạng ngoài.

Lần đầu chạy có thể mất khoảng 10 phút vì Docker cần build image và pull model `qwen3:4b`. Từ lần sau, model được cache trong Docker volume `ollama_data`.

Docker sẽ tự:

- Build web app image.
- Khởi động Ollama.
- Pull Qwen nếu volume chưa có model.
- Dùng sẵn `vectorstore/legal_vectorstore.json` trong repo.
- Mở web chatbot tại port `8000`.

Docker không tự crawl lại dữ liệu luật/DOCX mỗi lần chạy. Nếu bạn cập nhật dữ liệu, hãy chạy pipeline dữ liệu trước, rebuild vectorstore, sau đó build Docker lại.

### CPU Mode

`docker-compose.yml` mặc định chạy CPU-safe, không yêu cầu NVIDIA GPU:

```bash
docker compose up --build
```

### NVIDIA GPU Mode

Chạy thêm file override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### Change Qwen Model

PowerShell:

```powershell
$env:QWEN_MODEL="qwen3:8b"
docker compose up --build
```

Bash:

```bash
QWEN_MODEL=qwen3:8b docker compose up --build
```

## 💻 Local Installation

Use this path when you want to develop, debug retrieval, or rebuild data.

### Prerequisites

- Python 3.12+
- Ollama installed and running
- Git
- Microsoft Edge + Edge WebDriver if you want to crawl again

### Windows Setup

```powershell
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen3:4b
```

Run the web app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000
```

### macOS / Linux Setup

```bash
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
ollama pull qwen3:4b
```

Run the web app:

```bash
.venv/bin/python -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000
```

## ⚙️ Configuration

| Variable | Default | Mô tả |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` local, `http://ollama:11434` Docker | Ollama API endpoint |
| `QWEN_MODEL` | `qwen3:4b` | Model chat dùng để trả lời |
| `VECTORSTORE_PATH` | `vectorstore/legal_vectorstore.json` | Đường dẫn vectorstore |

Repo này không cần OpenAI API key hoặc API key cloud. Qwen chạy local qua Ollama.

## 🔐 Security & Privacy Notes

- ✅ Repo không cần OpenAI/Gemini/Anthropic API key hoặc secret cloud để chạy mặc định.
- ✅ `.env`, `.env.*`, `downloads/`, `drivers/`, cache và log runtime đã được ignore.
- ✅ Docker compose mặc định chỉ publish `8000` và `11434` trên `127.0.0.1`.
- ✅ Web UI render nguồn truy xuất bằng text node, tránh HTML injection từ nội dung chunk.
- ⚠️ Không nên public app trực tiếp lên internet nếu chưa thêm authentication/rate limit.
- ⚠️ `/api/retrieve` trả về full text chunk và metadata. Hiện dữ liệu là văn bản pháp luật public; nếu sau này ingest tài liệu nội bộ thì cần thêm phân quyền trước khi deploy.

## 📖 Usage Guide

### Web Chat

Start app, then open:

```text
http://localhost:8000
```

Ask questions such as:

```text
Ai không được thành lập doanh nghiệp?
```

```text
Mẫu số 1 Phụ lục I Thông tư 68/2025/TT-BTC gồm những nội dung gì?
```

```text
Hồ sơ đăng ký thay đổi nội dung đăng ký hộ kinh doanh gồm những mục nào?
```

### CLI Chat

Interactive mode:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py
```

Ask one question:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --question "Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?"
```

Retrieve only, useful for debugging chunks:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --retrieve-only --question "Mẫu số 2 Phụ lục II đăng ký thay đổi hộ kinh doanh gồm những mục nào?"
```

## 🧱 Data Pipeline

Vectorstore đã được commit sẵn, nên người dùng chỉ muốn chạy chatbot không cần chạy pipeline này.

Chỉ chạy lại khi:

- Muốn crawl lại văn bản luật.
- Muốn bổ sung biểu mẫu DOCX mới.
- Muốn thay đổi chunking.
- Muốn rebuild embedding/vectorstore.

### Step 1: Crawl Legal HTML

```powershell
.\.venv\Scripts\python.exe selenium_crawler.py
```

Output chính:

```text
legal_chunks.json
downloads/*.txt
```

### Step 2: Ingest TT68 DOCX Forms

```powershell
.\.venv\Scripts\python.exe tt68_forms_ingest.py
```

Script này đọc các file trong:

```text
downloads/tt68_forms_docx
```

Và cập nhật:

```text
legal_chunks.json
downloads/tt68_forms_coverage.json
```

### Step 3: Generate Data Audit

```powershell
.\.venv\Scripts\python.exe "Generate audit.py"
```

Output:

```text
legal_sources_audit.json
```

### Step 4: Build Vectorstore

```powershell
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

Output:

```text
vectorstore/legal_vectorstore.json
```

Important: whenever `legal_chunks.json` changes, run `step2_build_vectorstore.py` again.

### Step 5: Run Chatbot

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000
```

## 🔌 API Reference

| Endpoint | Method | Mô tả |
|---|---|---|
| `/` | GET | Web UI |
| `/health` | GET | Health check |
| `/api/chat` | POST | Hỏi chatbot, nhận câu trả lời và nguồn |
| `/api/retrieve` | POST | Chỉ truy xuất chunk, không gọi Qwen |
| `/docs` | GET | Swagger UI |

Example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Ai không được thành lập doanh nghiệp?", "top_k": 5}'
```

## 📚 Legal Data Coverage

Active vectorstore hiện có:

| Văn bản | Số chunk active | Ghi chú |
|---|---:|---|
| `67/VBHN-VPQH` | 224 | Văn bản hợp nhất Luật Doanh nghiệp 2025 |
| `76/2025/QH15` | 5 | Luật sửa đổi, bổ sung Luật Doanh nghiệp 2025 |
| `168/2025/NĐ-CP` | 133 | Nghị định hiện hành về đăng ký doanh nghiệp |
| `68/2025/TT-BTC` | 53 | Thông tư biểu mẫu đăng ký doanh nghiệp, hộ kinh doanh |

Inactive/historical chunks:

| Văn bản | Lý do |
|---|---|
| `01/2021/NĐ-CP` | Hết hiệu lực từ `01/07/2025`, bị thay thế bởi `168/2025/NĐ-CP` |
| `01/2021/TT-BKHĐT`, `02/2023/TT-BKHĐT` | Hết hiệu lực từ `01/07/2025`, bị thay thế bởi `68/2025/TT-BTC` |
| `59/2020/QH14`, `03/2022/QH15` | Giữ để đối chiếu lịch sử; nội dung đã hợp nhất trong `67/VBHN-VPQH` |

### TT68 Form Coverage

`68/2025/TT-BTC` hiện có:

- `5` chunk điều khoản/danh mục.
- `48` chunk nội dung chi tiết từ `33` biểu mẫu DOCX.
- Coverage chưa đủ 100% toàn bộ phụ lục.

Kiểm tra chi tiết tại:

```text
downloads/tt68_forms_coverage.json
```

Lưu ý quan trọng: PDF chính thức của TT68 là dạng scan/image, OCR tiếng Việt chưa đủ tin cậy để đưa thẳng vào RAG pháp luật từng câu từng chữ. Vì vậy repo chỉ ingest các DOCX chính thức tìm được, tránh đưa dữ liệu OCR sai vào chatbot.

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
├── Generate audit.py
├── legal_chunks.json
├── legal_sources_audit.json
├── vectorstore/
│   └── legal_vectorstore.json
└── downloads/
    ├── 68_2025_tt_btc.pdf
    ├── dkkd_doc_links.json
    ├── tt68_forms_docx/
    └── tt68_forms_coverage.json
```

## 🧪 Testing Your Setup

Test Ollama:

```bash
curl http://localhost:11434/api/tags
```

Test web app:

```bash
curl http://localhost:8000/health
```

Test retrieval only:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --retrieve-only --question "Mẫu số 1 Phụ lục I Thông tư 68/2025/TT-BTC gồm những nội dung gì?"
```

Expected behavior: top retrieved chunks should include `68_2025_tt_btc_phu_luc_i_mau_01`.

## 🛠️ Troubleshooting

### Docker is slow on CPU

This is expected. Qwen local inference on CPU can be several times slower than GPU. If you have NVIDIA GPU support, use:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

### Docker cannot find NVIDIA GPU

Use the default CPU compose instead:

```bash
docker compose up --build
```

The default `docker-compose.yml` does not require GPU.

### Chatbot says there is not enough context

That is usually correct behavior. The bot should not invent answers outside the legal chunks. Add/crawl the missing law source, rebuild vectorstore, then ask again.

### Updated legal_chunks.json but answers did not change

Rebuild vectorstore:

```powershell
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

Then restart the app.

### Ollama model missing

Pull the model:

```bash
ollama pull qwen3:4b
```

Or in Docker:

```bash
docker compose up --build
```

## 🚢 Deployment Notes

For local use:

```text
http://localhost:8000
```

Docker compose mặc định bind vào localhost. Nếu thật sự muốn dùng trong LAN, đổi port mapping thành `"8000:8000"` và đảm bảo firewall chỉ mở cho mạng tin cậy.

For production, place the app behind a reverse proxy, add authentication, and review legal-data update procedures carefully before exposing it publicly.
