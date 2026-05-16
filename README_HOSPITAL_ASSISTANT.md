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

## Thiết kế khác với form tham khảo

- Không gom thành `src/rag/*` theo từng khối textbook.
- Dùng `knowledge_base -> corpus_records -> faiss_store` như một vòng đời dữ liệu rõ ràng.
- PDF bảng giá được coi là nguồn tri thức hạng một, nạp trực tiếp từ thư mục local.
- Retrieval và answer layer giữ stateless để đơn giản hóa vận hành và dễ kiểm thử.
