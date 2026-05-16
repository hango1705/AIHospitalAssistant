from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from itertools import zip_longest
from pathlib import Path

import pdfplumber
from langchain_community.document_loaders import UnstructuredPDFLoader

from .schemas import CorpusBuildReport, CorpusRecord
from .settings import CORPUS_RECORDS_PATH, CORPUS_REPORT_PATH, DEFAULT_PDF_MODE, DEFAULT_PDF_STRATEGY, KB_PRICING_PDF_DIR, KNOWLEDGE_BASE_DIR, ensure_runtime_dirs


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _normalize_whitespace(value: str) -> str:
    text = str(value or "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _stable_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-").lower()
    return slug or "record"


def _content_hash(value: str) -> str:
    normalized = re.sub(r"\s+", " ", _normalize_whitespace(value).casefold())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _normalize_lookup(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower()).replace("đ", "d")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_price(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", _normalize_whitespace(value)))


def _find_matching_index(headers: list[str], *patterns: str) -> int | None:
    for index, header in enumerate(headers):
        for pattern in patterns:
            if pattern in header:
                return index
    return None


class HospitalKnowledgeBaseBuilder:
    def __init__(
        self,
        knowledge_base_dir: Path = KNOWLEDGE_BASE_DIR,
        pdf_dir: Path = KB_PRICING_PDF_DIR,
        pdf_mode: str = DEFAULT_PDF_MODE,
        pdf_strategy: str = DEFAULT_PDF_STRATEGY,
    ) -> None:
        self.knowledge_base_dir = knowledge_base_dir
        self.pdf_dir = pdf_dir
        self.pdf_mode = pdf_mode
        self.pdf_strategy = pdf_strategy
        ensure_runtime_dirs()
        self.documents_path = self.knowledge_base_dir / "documents.jsonl"
        self.tables_path = self.knowledge_base_dir / "tables.jsonl"

    def _document_records(self) -> tuple[list[CorpusRecord], int]:
        emitted: list[CorpusRecord] = []
        skipped = 0
        for raw in _read_jsonl(self.documents_path):
            title = _normalize_whitespace(raw.get("canonical_title") or raw.get("title") or raw.get("doc_id"))
            text = _normalize_whitespace(raw.get("text", ""))
            summary = _normalize_whitespace(raw.get("summary", ""))
            facts = [_normalize_whitespace(item) for item in raw.get("facts", []) if _normalize_whitespace(item)]
            contacts = [_normalize_whitespace(item) for item in raw.get("contact_points", []) if _normalize_whitespace(item)]

            sections: list[str] = [title]
            if summary and summary not in text:
                sections.append(f"Tóm tắt:\n{summary}")
            if facts:
                sections.append("Điểm tri thức:\n- " + "\n- ".join(facts))
            if contacts:
                sections.append("Thông tin liên hệ:\n- " + "\n- ".join(contacts))
            if text:
                sections.append(text)

            content = _normalize_whitespace("\n\n".join(part for part in sections if part))
            if len(content) < 80:
                skipped += 1
                continue

            emitted.append(
                CorpusRecord(
                    record_id=f"web-{raw['doc_id']}",
                    record_type="web_document",
                    title=title,
                    content=content,
                    topic_group=raw.get("topic_group") or "generic",
                    source_url=raw.get("source_url"),
                    content_hash=_content_hash(content),
                    metadata={
                        "doc_id": raw.get("doc_id"),
                        "page_type": raw.get("page_type"),
                        "breadcrumbs": raw.get("breadcrumbs", []),
                        "effective_date": raw.get("effective_date"),
                        "quality_flags": raw.get("quality_flags", []),
                    },
                )
            )
        return emitted, skipped

    def _table_records(self) -> tuple[list[CorpusRecord], int]:
        emitted: list[CorpusRecord] = []
        skipped = 0
        for raw in _read_jsonl(self.tables_path):
            columns = [_normalize_whitespace(col) for col in raw.get("columns", []) if _normalize_whitespace(col)]
            rows = raw.get("rows", [])
            if not columns or not rows:
                skipped += 1
                continue

            row_lines: list[str] = []
            for row in rows:
                parts = []
                for column in columns:
                    value = _normalize_whitespace(str(row.get(column, "")))
                    if value:
                        parts.append(f"{column}: {value}")
                if parts:
                    row_lines.append(" | ".join(parts))

            if not row_lines:
                skipped += 1
                continue

            title = _normalize_whitespace(raw.get("title") or raw.get("table_id"))
            header = " | ".join(columns)
            content = _normalize_whitespace(
                "\n\n".join(
                    [
                        f"Bảng dữ liệu: {title}",
                        f"Nguồn bảng: {raw.get('source_url', '')}",
                        f"Các cột: {header}",
                        "\n".join(row_lines),
                    ]
                )
            )
            emitted.append(
                CorpusRecord(
                    record_id=f"table-{raw['table_id']}",
                    record_type="table",
                    title=title,
                    content=content,
                    topic_group="pricing",
                    source_url=raw.get("source_url"),
                    content_hash=_content_hash(content),
                    metadata={
                        "table_id": raw.get("table_id"),
                        "doc_id": raw.get("doc_id"),
                        "columns": columns,
                        "extraction_method": raw.get("extraction_method"),
                    },
                )
            )
        return emitted, skipped

    def _pdf_records(self) -> tuple[list[CorpusRecord], int, int]:
        emitted: list[CorpusRecord] = []
        skipped = 0
        pdf_files_processed = 0
        if not self.pdf_dir.exists():
            return emitted, skipped, pdf_files_processed

        for pdf_path in sorted(self.pdf_dir.glob("*.pdf")):
            pdf_files_processed += 1
            loader = UnstructuredPDFLoader(
                str(pdf_path),
                mode=self.pdf_mode,
                strategy=self.pdf_strategy,
                languages=["vie", "eng"],
            )
            elements = loader.load()
            pages: dict[int, list[str]] = defaultdict(list)

            for element in elements:
                text = _normalize_whitespace(element.page_content)
                if not text:
                    continue
                metadata = element.metadata or {}
                category = _normalize_whitespace(str(metadata.get("category", "")))
                if category.lower() in {"header", "footer", "pagebreak"}:
                    continue
                page_number = int(metadata.get("page_number") or metadata.get("page") or 1)
                if not category or category in {"NarrativeText", "UncategorizedText"}:
                    rendered = text
                else:
                    rendered = f"{category}: {text}"
                if rendered not in pages[page_number]:
                    pages[page_number].append(rendered)

            if not pages:
                skipped += 1
                continue

            stem_slug = _stable_slug(pdf_path.stem)
            for page_number, lines in sorted(pages.items()):
                content = _normalize_whitespace("\n".join(lines))
                if len(content) < 80:
                    skipped += 1
                    continue
                emitted.append(
                    CorpusRecord(
                        record_id=f"pdf-{stem_slug}-page-{page_number:03d}",
                        record_type="pricing_pdf_page",
                        title=f"{pdf_path.stem} - Trang {page_number}",
                        content=content,
                        topic_group="pricing",
                        origin_path=str(pdf_path),
                        content_hash=_content_hash(content),
                        metadata={
                            "file_name": pdf_path.name,
                            "page_number": page_number,
                            "loader": "UnstructuredPDFLoader",
                            "mode": self.pdf_mode,
                            "strategy": self.pdf_strategy,
                        },
                    )
                )
        return emitted, skipped, pdf_files_processed

    def _pricing_service_records(self) -> tuple[list[CorpusRecord], int]:
        emitted: list[CorpusRecord] = []
        skipped = 0
        if not self.pdf_dir.exists():
            return emitted, skipped

        for pdf_path in sorted(self.pdf_dir.glob("*.pdf")):
            stem_slug = _stable_slug(pdf_path.stem)
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_number, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    if not tables:
                        continue

                    for table_index, table in enumerate(tables, start=1):
                        if not table or len(table) < 3:
                            continue

                        header_row_index = None
                        raw_headers: list[str] = []
                        for candidate_index, candidate_row in enumerate(table[:6]):
                            candidate_headers = [_normalize_whitespace(cell or "") for cell in candidate_row]
                            normalized_headers = [_normalize_lookup(header) for header in candidate_headers]
                            if any("gia dich vu" in header for header in normalized_headers) and any(
                                "stt" in header for header in normalized_headers
                            ):
                                header_row_index = candidate_index
                                raw_headers = candidate_headers
                                break

                        if header_row_index is None:
                            continue

                        headers = [_normalize_lookup(header) for header in raw_headers]
                        if not any("gia dich vu" in header for header in headers):
                            continue

                        stt_index = _find_matching_index(headers, "stt")
                        code_index = _find_matching_index(headers, "ma tuong duong", "ma tuong")
                        technical_name_index = _find_matching_index(
                            headers,
                            "ten dich vu ky thuat theo thong tu so 23 2024 tt byt",
                            "ten ky thuat theo thong tu so 23 2024 tt byt",
                        )
                        approved_name_index = _find_matching_index(headers, "ten dich vu phe duyet gia")
                        classification_index = _find_matching_index(headers, "phan loai")
                        price_index = _find_matching_index(headers, "gia dich vu")
                        note_index = _find_matching_index(headers, "ghi chu")

                        if price_index is None or (technical_name_index is None and approved_name_index is None):
                            continue

                        for row_index, row in enumerate(table[header_row_index + 1 :], start=1):
                            cells = [
                                _normalize_whitespace(value or "")
                                for _, value in zip_longest(raw_headers, row, fillvalue="")
                            ]
                            if not any(cells):
                                continue
                            if all(_normalize_lookup(cell) in {"1", "2", "3", "4", "5", "6", "7"} for cell in cells if cell):
                                continue

                            price = cells[price_index] if price_index < len(cells) else ""
                            if not _looks_like_price(price):
                                skipped += 1
                                continue

                            technical_name = cells[technical_name_index] if technical_name_index is not None and technical_name_index < len(cells) else ""
                            approved_name = cells[approved_name_index] if approved_name_index is not None and approved_name_index < len(cells) else ""
                            service_name = approved_name or technical_name
                            if not service_name:
                                skipped += 1
                                continue

                            stt = cells[stt_index] if stt_index is not None and stt_index < len(cells) else ""
                            code = cells[code_index] if code_index is not None and code_index < len(cells) else ""
                            classification = cells[classification_index] if classification_index is not None and classification_index < len(cells) else ""
                            note = cells[note_index] if note_index is not None and note_index < len(cells) else ""

                            parts = [
                                f"Dịch vụ: {service_name}",
                                f"Giá dịch vụ: {price} VNĐ",
                            ]
                            if technical_name and technical_name != service_name:
                                parts.append(f"Tên kỹ thuật: {technical_name}")
                            if code:
                                parts.append(f"Mã tương đương: {code}")
                            if classification:
                                parts.append(f"Phân loại: {classification}")
                            if note:
                                parts.append(f"Ghi chú: {note}")

                            content = _normalize_whitespace("\n".join(parts))
                            emitted.append(
                                CorpusRecord(
                                    record_id=f"pricing-service-{stem_slug}-page-{page_number:03d}-table-{table_index:02d}-row-{row_index:03d}",
                                    record_type="pricing_pdf_service",
                                    title=service_name,
                                    content=content,
                                    topic_group="pricing",
                                    origin_path=str(pdf_path),
                                    content_hash=_content_hash(content),
                                    metadata={
                                        "file_name": pdf_path.name,
                                        "page_number": page_number,
                                        "table_index": table_index,
                                        "row_index": row_index,
                                        "service_name": service_name,
                                        "technical_name": technical_name,
                                        "approved_name": approved_name,
                                        "price": price,
                                        "code": code,
                                        "classification": classification,
                                        "note": note,
                                        "loader": "UnstructuredPDFLoader+pdfplumber",
                                    },
                                )
                            )

        return emitted, skipped

    def build_records(self) -> tuple[list[CorpusRecord], CorpusBuildReport]:
        all_records: list[CorpusRecord] = []
        duplicates_removed = 0

        web_records, skipped_web = self._document_records()
        table_records, skipped_tables = self._table_records()
        pdf_records, skipped_pdfs, pdf_files_processed = self._pdf_records()
        pricing_service_records, skipped_pricing_services = self._pricing_service_records()

        all_records.extend(web_records)
        all_records.extend(table_records)
        all_records.extend(pdf_records)
        all_records.extend(pricing_service_records)

        deduped: list[CorpusRecord] = []
        seen_hashes: set[str] = set()
        for record in all_records:
            if record.content_hash in seen_hashes:
                duplicates_removed += 1
                continue
            seen_hashes.add(record.content_hash)
            deduped.append(record)

        report = CorpusBuildReport(
            knowledge_base_dir=str(self.knowledge_base_dir),
            records_written=len(deduped),
            web_records=len(web_records),
            table_records=len(table_records),
            pdf_records=len(pdf_records),
            pricing_service_records=len(pricing_service_records),
            pdf_files_processed=pdf_files_processed,
            duplicates_removed=duplicates_removed,
            empty_records_skipped=skipped_web + skipped_tables + skipped_pdfs + skipped_pricing_services,
            output_path=str(CORPUS_RECORDS_PATH),
        )
        return deduped, report

    def build_and_save(self) -> CorpusBuildReport:
        records, report = self.build_records()
        _write_jsonl(CORPUS_RECORDS_PATH, [record.model_dump() for record in records])
        _write_json(CORPUS_REPORT_PATH, report.model_dump())
        return report
