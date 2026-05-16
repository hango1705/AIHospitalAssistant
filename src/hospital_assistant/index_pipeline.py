from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .kb_pipeline import HospitalKnowledgeBaseBuilder
from .schemas import CorpusRecord, IndexBuildReport
from .settings import (
    CHUNK_MANIFEST_PATH,
    CORPUS_RECORDS_PATH,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    FAISS_REPORT_PATH,
    FAISS_STORE_DIR,
    ensure_runtime_dirs,
    env_or_default,
    load_env_file,
)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class HospitalIndexPipeline:
    def __init__(self, corpus_path: Path = CORPUS_RECORDS_PATH, store_dir: Path = FAISS_STORE_DIR) -> None:
        self.corpus_path = corpus_path
        self.store_dir = store_dir
        ensure_runtime_dirs()

    def _faiss_io_dir(self) -> Path:
        base_dir = Path(tempfile.gettempdir()) / f"hospital_assistant_faiss_io_{uuid4().hex}"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    def load_corpus_records(self) -> list[CorpusRecord]:
        if not self.corpus_path.exists():
            HospitalKnowledgeBaseBuilder().build_and_save()
        return [CorpusRecord.model_validate(item) for item in _read_jsonl(self.corpus_path)]

    def _base_document(self, record: CorpusRecord) -> Document:
        metadata = {
            "record_id": record.record_id,
            "record_type": record.record_type,
            "title": record.title,
            "topic_group": record.topic_group,
            "source_url": record.source_url or "",
            "origin_path": record.origin_path or "",
            **record.metadata,
        }
        return Document(page_content=record.content, metadata=metadata)

    def chunk_records(
        self,
        records: list[CorpusRecord],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks: list[Document] = []
        for record in records:
            if record.record_type == "pricing_pdf_service":
                chunk = self._base_document(record)
                chunk.metadata["chunk_id"] = f"{record.record_id}::chunk-001"
                chunks.append(chunk)
                continue
            split_docs = splitter.split_documents([self._base_document(record)])
            for index, chunk in enumerate(split_docs, start=1):
                chunk.metadata["chunk_id"] = f"{record.record_id}::chunk-{index:03d}"
                chunks.append(chunk)
        return chunks

    def build_index(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        embedding_model: str | None = None,
        reset: bool = False,
    ) -> IndexBuildReport:
        load_env_file()
        embedding_model = embedding_model or env_or_default("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        records = self.load_corpus_records()
        chunks = self.chunk_records(records, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if reset and self.store_dir.exists():
            shutil.rmtree(self.store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        embeddings = OpenAIEmbeddings(model=embedding_model)
        vector_store = FAISS.from_documents(chunks, embeddings)
        io_dir = self._faiss_io_dir()
        vector_store.save_local(str(io_dir))
        for filename in ("index.faiss", "index.pkl"):
            shutil.copy2(io_dir / filename, self.store_dir / filename)

        _write_jsonl(
            CHUNK_MANIFEST_PATH,
            [
                {
                    "chunk_id": chunk.metadata["chunk_id"],
                    "title": chunk.metadata.get("title"),
                    "record_type": chunk.metadata.get("record_type"),
                    "source_url": chunk.metadata.get("source_url"),
                    "origin_path": chunk.metadata.get("origin_path"),
                    "page_number": chunk.metadata.get("page_number"),
                    "content": chunk.page_content,
                    "metadata": dict(chunk.metadata),
                }
                for chunk in chunks
            ],
        )

        report = IndexBuildReport(
            corpus_path=str(self.corpus_path),
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            source_records=len(records),
            chunks_written=len(chunks),
            faiss_store_dir=str(self.store_dir),
        )
        _write_json(FAISS_REPORT_PATH, report.model_dump())
        return report

    def load_vector_store(self, embedding_model: str | None = None) -> FAISS:
        load_env_file()
        embedding_model = embedding_model or env_or_default("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        embeddings = OpenAIEmbeddings(model=embedding_model)
        io_dir = self._faiss_io_dir()
        for filename in ("index.faiss", "index.pkl"):
            shutil.copy2(self.store_dir / filename, io_dir / filename)
        return FAISS.load_local(
            str(io_dir),
            embeddings,
            allow_dangerous_deserialization=True,
        )
