from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
CATALOG_DIR = DATA_DIR / "catalog"
RAW_DIR = DATA_DIR / "raw"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
INDEX_DIR = DATA_DIR / "index"

KB_DOCUMENTS_PATH = KNOWLEDGE_BASE_DIR / "documents.jsonl"
KB_TABLES_PATH = KNOWLEDGE_BASE_DIR / "tables.jsonl"
KB_ASSETS_PATH = KNOWLEDGE_BASE_DIR / "assets.jsonl"
KB_CANONICAL_DIR = KNOWLEDGE_BASE_DIR / "canonical_docs"
KB_PRICING_PDF_DIR = KNOWLEDGE_BASE_DIR / "bang_gia"

CORPUS_RECORDS_PATH = INDEX_DIR / "corpus_records.jsonl"
CORPUS_REPORT_PATH = INDEX_DIR / "corpus_report.json"
CHUNK_MANIFEST_PATH = INDEX_DIR / "chunk_manifest.jsonl"
FAISS_STORE_DIR = INDEX_DIR / "faiss_store"
FAISS_REPORT_PATH = INDEX_DIR / "faiss_report.json"

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 140
DEFAULT_RETRIEVAL_K = 6
DEFAULT_RETRIEVAL_FETCH_K = 18
DEFAULT_RETRIEVAL_LAMBDA = 0.55
DEFAULT_PDF_STRATEGY = "fast"
DEFAULT_PDF_MODE = "elements"


def ensure_runtime_dirs() -> None:
    for path in (INDEX_DIR, FAISS_STORE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_env_file(env_path: Path | None = None) -> None:
    target = env_path or (ROOT_DIR / ".env")
    if not target.exists():
        return
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def env_or_default(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def env_int_or_default(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def database_path_from_env() -> Path:
    value = env_or_default("DATABASE_URL", "sqlite:///data/app/app.sqlite3")
    if value.startswith("sqlite:///"):
        raw_path = value.removeprefix("sqlite:///")
    elif value.startswith("sqlite://"):
        raw_path = value.removeprefix("sqlite://")
    else:
        raw_path = value
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT_DIR / path
