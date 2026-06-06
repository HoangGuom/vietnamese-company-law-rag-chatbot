# RAG Chatbot Luật Doanh Nghiệp

Project này gồm 3 bước chính:

1. Crawl và tách văn bản luật thành chunks:

```powershell
.\.venv\Scripts\python.exe selenium_crawler.py
```

2. Build vector store bằng dense embedding:

```powershell
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

3. Chat RAG với Qwen:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py
```

Hỏi một câu rồi thoát:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --question "Điều kiện thành lập công ty TNHH là gì?"
```

Chỉ kiểm tra truy xuất tài liệu, không gọi Qwen:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --retrieve-only --question "Hồ sơ đăng ký doanh nghiệp gồm những gì?"
```

## Qwen

Mặc định chatbot gọi Qwen3 qua Ollama:

```powershell
ollama pull qwen3:4b
ollama serve
```

Nếu terminal vừa cài Ollama xong mà chưa nhận lệnh `ollama`, mở terminal mới hoặc dùng:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

Đổi model:

```powershell
.\.venv\Scripts\python.exe step3_rag_chatbot.py --model qwen3:8b
```

Hoặc đặt biến môi trường:

```powershell
$env:QWEN_MODEL="qwen3:4b"
$env:OLLAMA_URL="http://localhost:11434"
```

## Ghi chú dữ liệu

`legal_chunks.json` hiện có dữ liệu từ 9 văn bản. Khi kiểm tra, văn bản `01/2021/NĐ-CP` chỉ parse được 14 điều trong khi code kỳ vọng tối thiểu 80 điều, nên nguồn tải về có thể chưa phải toàn văn.

## Chạy Web App

Chạy web app trên máy local:

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_web_app:app --host 0.0.0.0 --port 8000
```

Mở:

```text
http://localhost:8000
```

API chat:

```powershell
curl -X POST http://localhost:8000/api/chat `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"Điều kiện cấp Giấy chứng nhận đăng ký doanh nghiệp là gì?\",\"top_k\":5}"
```

## Triển khai Docker

Trước khi build Docker, bảo đảm đã có vector store:

```powershell
.\.venv\Scripts\python.exe step2_build_vectorstore.py
```

Chạy full stack bằng Docker Compose:

```powershell
docker info
docker compose up --build
```

Nếu `docker info` báo không kết nối được Docker API, hãy mở Docker Desktop trước rồi chạy lại.

Compose sẽ chạy:

- `ollama`: server Qwen.
- `ollama-pull`: tải `qwen3:4b` vào volume Docker nếu chưa có.
- `rag-chatbot`: web/API chatbot ở `http://localhost:8000`.

Nếu muốn đổi model:

```powershell
$env:QWEN_MODEL="qwen3:8b"
docker compose up --build
```

Với NVIDIA GPU, Docker Desktop cần bật WSL 2 backend và GPU support. Nếu máy người dùng không có GPU, Ollama vẫn có thể chạy CPU nhưng sẽ chậm hơn.

## Chia sẻ cho người khác

Người khác chỉ cần:

1. Cài Docker Desktop.
2. Clone/copy project này.
3. Chạy `docker compose up --build`.
4. Mở `http://localhost:8000`.

Nếu muốn người khác trong cùng mạng LAN truy cập máy đang chạy chatbot, mở firewall cho port `8000` và dùng địa chỉ IP của máy host:

```text
http://<IP-may-host>:8000
```
