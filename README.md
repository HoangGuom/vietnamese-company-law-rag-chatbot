# RAG Chatbot Luật Doanh Nghiệp

Chatbot tra cứu pháp luật doanh nghiệp Việt Nam, sử dụng RAG (Retrieval-Augmented Generation) với Qwen3 qua Ollama.

---

## Chạy nhanh bằng Docker (khuyến nghị)

> Yêu cầu: [Docker Desktop](https://www.docker.com/products/docker-desktop/) đã cài và đang chạy.

```bash
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
docker compose up --build
```

Lần đầu chạy mất ~10 phút (build image + pull model `qwen3:4b` ~2.5 GB).  
Từ lần 2 trở đi chỉ mất ~30 giây vì model đã được cache trong Docker volume.

Mở trình duyệt:
```
http://localhost:8000
```

### Máy không có GPU

Mở `docker-compose.yml`, xóa hoặc comment khối `deploy:` trong service `ollama`:

```yaml
# deploy:           ← xóa/comment 6 dòng này
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: all
#           capabilities: [gpu]
```

Ollama vẫn chạy bình thường bằng CPU, chỉ chậm hơn ~5–10 lần.

### Đổi model Qwen

```bash
QWEN_MODEL=qwen3:8b docker compose up --build
```

---

## Chạy trên máy local (không dùng Docker)

### Yêu cầu

- Python 3.12+
- [Ollama](https://ollama.com/) đã cài và đang chạy

### Cài đặt

```bash
git clone https://github.com/HoangGuom/vietnamese-company-law-rag-chatbot.git
cd vietnamese-company-law-rag-chatbot
python -m venv .venv
```

**Windows:**
```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Pull model Qwen

```bash
ollama pull qwen3:4b
```

### Chạy web app

```bash
# Windows
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000

# macOS / Linux
.venv/bin/python -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000
```

Mở `http://localhost:8000`.

---

## Các bước xây dựng pipeline (tùy chọn)

Pipeline gồm 3 bước — **vectorstore đã được commit sẵn**, bạn không cần chạy lại trừ khi muốn cập nhật dữ liệu.

### Bước 1 — Crawl văn bản luật

```bash
# Yêu cầu: Microsoft Edge + Edge WebDriver
.\.venv\Scripts\python.exe selenium_crawler.py
```

### Bước 2 — Build vectorstore

```bash
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

### Bước 3 — Chat RAG qua CLI

```bash
# Chat tương tác
.\.venv\Scripts\python.exe step3_rag_chatbot.py

# Hỏi một câu rồi thoát
.\.venv\Scripts\python.exe step3_rag_chatbot.py --question "Điều kiện thành lập công ty TNHH là gì?"

# Chỉ kiểm tra truy xuất, không gọi Qwen
.\.venv\Scripts\python.exe step3_rag_chatbot.py --retrieve-only --question "Hồ sơ đăng ký doanh nghiệp gồm những gì?"
```

---

## API

| Endpoint | Method | Mô tả |
|---|---|---|
| `/` | GET | Giao diện web |
| `/health` | GET | Trạng thái server |
| `/api/chat` | POST | Hỏi chatbot, nhận câu trả lời + nguồn |
| `/api/retrieve` | POST | Chỉ truy xuất chunks, không gọi Qwen |
| `/docs` | GET | Swagger UI |

Ví dụ gọi API:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?", "top_k": 5}'
```

---

## Dữ liệu pháp luật

Trạng thái hiệu lực của các văn bản được ghi trong `legal_sources_audit.json`.

Vectorstore hiện hành đang dùng:

- `67/VBHN-VPQH` — văn bản hợp nhất Luật Doanh nghiệp 2025
- `76/2025/QH15` — Luật sửa đổi, bổ sung Luật Doanh nghiệp 2025
- `168/2025/NĐ-CP` — Nghị định hiện hành về đăng ký doanh nghiệp

Các văn bản không dùng cho RAG hiện hành:

- `01/2021/NĐ-CP` — hết hiệu lực từ `01/07/2025`, bị thay thế bởi `168/2025/NĐ-CP`
- `01/2021/TT-BKHĐT`, `02/2023/TT-BKHĐT` — hết hiệu lực từ `01/07/2025`, bị thay thế bởi `68/2025/TT-BTC`
- `59/2020/QH14`, `03/2022/QH15` — giữ để đối chiếu lịch sử, nội dung đã hợp nhất trong `67/VBHN-VPQH`

> **Còn thiếu:** `68/2025/TT-BTC` chưa được crawl. Chatbot chưa trả lời được sâu về biểu mẫu đăng ký doanh nghiệp.

---

## Chia sẻ cho người khác trong mạng LAN

Mở firewall cho port `8000` trên máy host, sau đó người dùng khác truy cập:

```
http://<IP-may-host>:8000
```
