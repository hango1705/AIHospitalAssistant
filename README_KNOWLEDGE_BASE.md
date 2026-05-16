# Knowledge Base Pipeline

This project builds only the Knowledge Base layer for a hospital website.

Outputs:
- `data/catalog`: crawl seeds, katana discovery, source inventory, reports
- `data/raw/html`: fetched HTML pages
- `data/raw/assets`: downloaded images
- `data/raw/embeds`: downloaded PDF/XLSX/DOCX/TXT resources
- `data/knowledge_base/documents.jsonl`: normalized knowledge documents
- `data/knowledge_base/tables.jsonl`: extracted tables
- `data/knowledge_base/assets.jsonl`: asset inventory
- `data/knowledge_base/canonical_docs`: markdown review copies of normalized documents

This pipeline does not perform:
- chunking
- embedding
- vector database ingestion
- retrieval
- question answering

Run:

```powershell
.\.venv\Scripts\python .\scripts\collect_bv_a_data.py --mode smoke
.\.venv\Scripts\python .\scripts\collect_bv_a_data.py --mode full
```
