from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmbeddedResource(BaseModel):
    kind: Literal["image", "iframe", "file"]
    source_url: str
    resolved_url: str | None = None
    local_path: str | None = None
    mime_type: str | None = None
    status: str = "pending"
    note: str | None = None


class ExtractedTable(BaseModel):
    table_id: str
    doc_id: str
    title: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    source_url: str
    extraction_method: str


class KnowledgeDocument(BaseModel):
    doc_id: str
    source_url: str
    page_type: str
    topic_group: str
    title: str
    canonical_title: str
    breadcrumbs: list[str] = Field(default_factory=list)
    text: str = ""
    summary: str = ""
    department: str | None = None
    service: str | None = None
    published_at: str | None = None
    effective_date: str | None = None
    contact_points: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    assets: list[EmbeddedResource] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    source_status: str = "ok"


class SourceRecord(BaseModel):
    source_url: str
    page_type: str
    topic_group: str
    title: str | None = None
    discovered_from: str | None = None
    source_tag: str | None = None
    source_attribute: str | None = None
    status_code: int | None = None
    content_length: int | None = None
    crawl_status: str = "pending"
    note: str | None = None


class PipelineReport(BaseModel):
    mode: str
    katana_depth: int
    crawl_duration: str
    sources_discovered: int
    sources_selected: int
    documents_written: int
    tables_written: int
    errors: int
