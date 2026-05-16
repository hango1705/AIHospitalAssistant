# Hospital Assistant Pipeline

Pipeline này triển khai phần việc tương ứng tuần 4, 5, 6 cho đề tài chatbot hỗ trợ bệnh nhân tại Bệnh viện A Thái Nguyên, nhưng theo cách tổ chức khác với form tách module kiểu mẫu.

## Cấu trúc dữ liệu

- `data/catalog`: báo cáo crawl và inventory URL.
- `data/raw`: HTML, ảnh và embed gốc để truy vết.
- `data/knowledge_base`: knowledge base đã làm sạch.
- `data/index`: corpus records, chunk manifest và FAISS store.

Knowledge base đầu vào:

- `data/knowledge_base/documents.jsonl`: tri thức web đã chuẩn hóa.
- `data/knowledge_base/tables.jsonl`: bảng trích xuất.
- `data/knowledge_base/assets.jsonl`: inventory asset.
- `data/knowledge_base/bang_gia/*.pdf`: bộ PDF bảng giá tải tay, được nạp bằng `UnstructuredPDFLoader`.

## Ánh xạ theo tiến độ

- Tuần 4: chuẩn hóa knowledge base, đưa PDF vào corpus, dedupe và chunking.
- Tuần 5: embedding và xây FAISS local index, thêm script kiểm tra retrieval.
- Tuần 6: hỏi đáp bằng `ChatOpenAI` với retrieval theo MMR và trích dẫn nguồn.

## Thư viện chính

- `langchain-text-splitters`
- `langchain-community`
- `langchain-openai`
- `langchain-core`
- `faiss-cpu`
- `unstructured`
- `pypdf`

## Cài đặt

```powershell
.\.venv\Scripts\python -m pip install -r .\requirements.txt
```

## 1. Xây corpus tuần 4

```powershell
.\.venv\Scripts\python .\scripts\build_hospital_corpus.py
```

Đầu ra:

- `data/index/corpus_records.jsonl`
- `data/index/corpus_report.json`

## 2. Build FAISS tuần 5

```powershell
.\.venv\Scripts\python .\scripts\build_faiss_index.py --reset
```

Đầu ra:

- `data/index/faiss_store`
- `data/index/chunk_manifest.jsonl`
- `data/index/faiss_report.json`

## 3. Kiểm tra retrieval tuần 5

```powershell
.\.venv\Scripts\python .\scripts\check_hospital_retrieval.py `
  --query "Quy trình khám bệnh bảo hiểm y tế như thế nào?"
```

## 4. Hỏi đáp tuần 6

Single question:

```powershell
.\.venv\Scripts\python .\scripts\chat_hospital_assistant.py `
  --question "Bệnh viện A Thái Nguyên có số điện thoại liên hệ nào?"
```

Interactive:

```powershell
.\.venv\Scripts\python .\scripts\chat_hospital_assistant.py
```

## 5. Chạy FastAPI backend cho mobile app

Backend local bọc pipeline RAG hiện có để Android app gọi qua HTTP.

Tạo cấu hình local từ mẫu:

```powershell
Copy-Item .\.env.example .\.env
```

Các biến quan trọng:

- `OPENAI_API_KEY`: bắt buộc khi build lại FAISS hoặc chatbot cần gọi LLM.
- `DATABASE_URL`: mặc định `sqlite:///data/app/app.sqlite3`.
- `ACCESS_TOKEN_TTL_MINUTES`: thời hạn token đăng nhập, mặc định 480 phút.
- `PASSWORD_MIN_LENGTH`: tối thiểu 8 ký tự; đăng ký mới phải có cả chữ và số.
- `DEFAULT_ADMIN_USERNAME`, `DEFAULT_ADMIN_PASSWORD`: tài khoản admin local mặc định đang là `admin/admin`. Khi đóng gói bản gần production, đổi mật khẩu này trong `.env` trước lần chạy DB đầu tiên.

Chạy server:

```powershell
.\.venv\Scripts\python -m uvicorn hospital_assistant.api:app `
  --app-dir src `
  --host 0.0.0.0 `
  --port 8000
```

Kiểm tra health:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Gửi câu hỏi:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"Bệnh viện A Thái Nguyên ở đâu?","context_hint":null}'
```

Android emulator dùng base URL `http://10.0.2.2:8000`. Điện thoại thật dùng IP LAN của laptop đang chạy backend.

## 6. Vận hành các tính năng gần production

- Auth: token có thời hạn và logout sẽ thu hồi token server-side. Nếu token hết hạn, app cần đăng nhập lại.
- User đăng ký mới luôn có role `patient`; admin mặc định được seed từ `.env`.
- Lịch sử chat: backend lưu theo từng cuộc trò chuyện. Android có thể tạo cuộc trò chuyện mới, chọn lại cuộc trò chuyện cũ và xóa từng cuộc trò chuyện.
- Đặt lịch khám: user xem lịch của mình; admin xem toàn bộ lịch và đổi trạng thái `pending`, `confirmed`, `cancelled`.
- Admin cập nhật knowledge base: admin tạo job trong dashboard. Backend chạy pipeline `scripts/build_hospital_corpus.py` rồi `scripts/build_faiss_index.py --reset`, lưu log vào DB và reload assistant cache sau khi thành công.

Backup DB local:

```powershell
Copy-Item .\data\app\app.sqlite3 ".\data\app\app.backup.sqlite3"
```

## Thiết kế khác với form tham khảo

- Không gom thành `src/rag/*` theo từng khối textbook.
- Dùng `knowledge_base -> corpus_records -> faiss_store` như một vòng đời dữ liệu rõ ràng.
- PDF bảng giá được coi là nguồn tri thức hạng một, nạp trực tiếp từ thư mục local.
- Retrieval và answer layer giữ stateless để đơn giản hóa vận hành và dễ kiểm thử.
