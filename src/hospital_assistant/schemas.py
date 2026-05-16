from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CorpusRecord(BaseModel):
    record_id: str
    record_type: Literal["web_document", "table", "pricing_pdf_page", "pricing_pdf_service"]
    title: str
    content: str
    topic_group: str = "generic"
    source_url: str | None = None
    origin_path: str | None = None
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusBuildReport(BaseModel):
    knowledge_base_dir: str
    records_written: int
    web_records: int
    table_records: int
    pdf_records: int
    pricing_service_records: int
    pdf_files_processed: int
    duplicates_removed: int
    empty_records_skipped: int
    output_path: str


class IndexBuildReport(BaseModel):
    corpus_path: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    source_records: int
    chunks_written: int
    faiss_store_dir: str


class RetrievedSource(BaseModel):
    source_id: str
    title: str
    locator: str
    source_url: str | None = None
    origin_path: str | None = None
    record_type: str
    chunk_id: str


class AnswerResult(BaseModel):
    question: str
    answer: str
    sources: list[RetrievedSource] = Field(default_factory=list)
