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

## Ghi chú dữ liệu pháp luật

Trạng thái hiệu lực của các văn bản được ghi trong `legal_sources_audit.json`.
`legal_chunks.json` vẫn giữ cả văn bản lịch sử để đối chiếu, nhưng khi build
vectorstore mặc định `step2_build_vectorstore.py` chỉ lấy các chunk có
`su_dung_cho_rag=true`.

Vectorstore hiện hành đang dùng:

- `67/VBHN-VPQH`: văn bản hợp nhất Luật Doanh nghiệp 2025.
- `76/2025/QH15`: Luật sửa đổi, bổ sung Luật Doanh nghiệp 2025.
- `168/2025/NĐ-CP`: Nghị định hiện hành về đăng ký doanh nghiệp.

Các văn bản không dùng cho RAG hiện hành:

- `01/2021/NĐ-CP`: hết hiệu lực toàn bộ từ `01/07/2025`, bị thay thế bởi `168/2025/NĐ-CP`.
- `01/2021/TT-BKHĐT` và `02/2023/TT-BKHĐT`: hết hiệu lực từ `01/07/2025`, bị thay thế bởi `68/2025/TT-BTC`.
- `6568/VBHN-BKHĐT`: không dùng cho hiện hành vì hợp nhất nhóm thông tư cũ đã hết hiệu lực.
- `59/2020/QH14` và `03/2022/QH15`: giữ để đối chiếu lịch sử, nhưng không embed mặc định vì nội dung hiện hành đã được hợp nhất trong `67/VBHN-VPQH`.

`68/2025/TT-BTC` đã được xác định là văn bản hiện hành, nhưng chưa có chunk trong
dataset hiện tại. Nên crawl bổ sung văn bản này nếu muốn chatbot trả lời sâu về
biểu mẫu đăng ký doanh nghiệp, đăng ký hộ kinh doanh.

Nguồn ưu tiên khi kiểm tra hiệu lực: `congbao.chinhphu.vn`,
`vanban.chinhphu.vn`, `vbpl.vn`. `thuvienphapluat.vn` chỉ nên dùng làm nguồn
tham khảo/fallback.

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
