from __future__ import annotations

from difflib import SequenceMatcher
import json
import re
from pathlib import Path

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .index_pipeline import HospitalIndexPipeline
from .schemas import AnswerResult, RetrievedSource
from .settings import (
    CHUNK_MANIFEST_PATH,
    DEFAULT_LLM_MODEL,
    DEFAULT_RETRIEVAL_FETCH_K,
    DEFAULT_RETRIEVAL_K,
    DEFAULT_RETRIEVAL_LAMBDA,
    FAISS_STORE_DIR,
    KB_TABLES_PATH,
    env_or_default,
    load_env_file,
)


def _stringify_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def _normalize_match(value: str) -> str:
    text = value.lower()
    replacements = str.maketrans(
        {
            "đ": "d",
            "á": "a",
            "à": "a",
            "ả": "a",
            "ã": "a",
            "ạ": "a",
            "ă": "a",
            "ắ": "a",
            "ằ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "ặ": "a",
            "â": "a",
            "ấ": "a",
            "ầ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ậ": "a",
            "é": "e",
            "è": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ẹ": "e",
            "ê": "e",
            "ế": "e",
            "ề": "e",
            "ể": "e",
            "ễ": "e",
            "ệ": "e",
            "í": "i",
            "ì": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ị": "i",
            "ó": "o",
            "ò": "o",
            "ỏ": "o",
            "õ": "o",
            "ọ": "o",
            "ô": "o",
            "ố": "o",
            "ồ": "o",
            "ổ": "o",
            "ỗ": "o",
            "ộ": "o",
            "ơ": "o",
            "ớ": "o",
            "ờ": "o",
            "ở": "o",
            "ỡ": "o",
            "ợ": "o",
            "ú": "u",
            "ù": "u",
            "ủ": "u",
            "ũ": "u",
            "ụ": "u",
            "ư": "u",
            "ứ": "u",
            "ừ": "u",
            "ử": "u",
            "ữ": "u",
            "ự": "u",
            "ý": "y",
            "ỳ": "y",
            "ỷ": "y",
            "ỹ": "y",
            "ỵ": "y",
        }
    )
    text = text.translate(replacements)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize_for_bm25(value: str) -> list[str]:
    return [token for token in _normalize_match(value).split() if token]


def _normalize_noisy_token(token: str) -> str:
    value = _normalize_match(token)
    if not value:
        return ""
    value = re.sub(r"(.)\1{1,}", r"\1", value)
    if len(value) > 3:
        value = re.sub(r"(?:s|f|r|x|j|z|w)+$", "", value)
    value = (
        value.replace("dd", "d")
        .replace("aa", "a")
        .replace("ee", "e")
        .replace("ii", "i")
        .replace("oo", "o")
        .replace("uu", "u")
        .replace("yy", "y")
        .replace("ow", "o")
        .replace("uw", "u")
    )
    value = re.sub(r"(.)\1{1,}", r"\1", value)
    return value.strip()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class HospitalAssistant:
    def __init__(
        self,
        store_dir: Path = FAISS_STORE_DIR,
        llm_model: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        load_env_file()
        self.llm_model = llm_model or env_or_default("OPENAI_LLM_MODEL", DEFAULT_LLM_MODEL)
        self.index = HospitalIndexPipeline(store_dir=store_dir)
        self.vector_store = self.index.load_vector_store(embedding_model=embedding_model)
        self.chunk_manifest = _read_jsonl(CHUNK_MANIFEST_PATH)
        self.kb_tables = _read_jsonl(KB_TABLES_PATH)
        self.manifest_docs = [self._build_manifest_doc(item) for item in self.chunk_manifest]
        self.keyword_retriever = BM25Retriever.from_documents(
            self.manifest_docs,
            preprocess_func=_tokenize_for_bm25,
        )
        self.pricing_service_docs = [
            doc for doc in self.manifest_docs if str((doc.metadata or {}).get("record_type", "")) == "pricing_pdf_service"
        ]
        self.llm = ChatOpenAI(model=self.llm_model, temperature=0)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Bạn là trợ lý hỗ trợ bệnh nhân của Bệnh viện A Thái Nguyên.\n"
                    "Chỉ được dùng thông tin có trong ngữ cảnh đã truy xuất.\n"
                    "Nếu ngữ cảnh không đủ, hãy trả lời đúng câu: "
                    "\"Tôi chưa tìm thấy thông tin phù hợp trong cơ sở tri thức hiện có.\".\n"
                    "Trả lời bằng tiếng Việt rõ ràng, ngắn gọn, không bịa thêm chi tiết.\n"
                    "Khi dùng thông tin từ ngữ cảnh, hãy gắn trích dẫn inline dạng [Nguon 1], [Nguon 2].",
                ),
                (
                    "human",
                    "Câu hỏi:\n{question}\n\n"
                    "Ngữ cảnh truy xuất:\n{context}\n\n"
                    "Không dùng thông tin của khoa/phòng để trả lời cho địa chỉ hoặc thông tin liên hệ cấp bệnh viện, trừ khi câu hỏi hỏi rõ tên khoa/phòng.\n"
                    "Hãy trả lời cho người dùng và giữ nguyên định dạng trích dẫn [Nguon X].",
                ),
            ]
        )

    def _compose_search_query(self, question: str, context_hint: str | None = None) -> str:
        if not context_hint:
            return question
        normalized_question = _normalize_match(question)
        normalized_hint = _normalize_match(context_hint)
        if normalized_hint and normalized_hint in normalized_question:
            return question
        return f"{context_hint}\n{question}"

    def _is_hospital_level_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return "benh vien a" in normalized and not any(
            token in normalized
            for token in (
                "khoa ",
                "phong ",
                "trung tam ",
                "da lieu",
                "nhi",
                "san",
                "giai phau benh",
                "rang ham mat",
            )
        )

    def _is_address_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return any(token in normalized for token in ("dia chi", "o dau", "nam o dau", "dia diem"))

    def _is_phone_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return any(token in normalized for token in ("so dien thoai", "dien thoai", "hotline", "lien he"))

    def _is_email_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return "email" in normalized or "mail" in normalized

    def _build_manifest_doc(self, item: dict) -> Document:
        manifest_metadata = dict(item.get("metadata") or {})
        manifest_metadata.update(
            {
                "chunk_id": item.get("chunk_id", ""),
                "title": item.get("title", ""),
                "source_url": item.get("source_url", ""),
                "origin_path": item.get("origin_path", ""),
                "record_type": item.get("record_type", ""),
                "page_number": item.get("page_number"),
            }
        )
        return Document(
            page_content=str(item.get("content", "")),
            metadata=manifest_metadata,
        )

    def _hospital_profile_candidates(self, question: str, limit: int = 4) -> list[Document]:
        normalized_question = _normalize_match(question)
        address_query = self._is_address_query(question)
        phone_query = self._is_phone_query(question)
        email_query = self._is_email_query(question)
        scored: list[tuple[int, dict]] = []

        for item in self.chunk_manifest:
            source_url = str(item.get("source_url", ""))
            title = str(item.get("title", ""))
            content = str(item.get("content", ""))
            normalized_content = _normalize_match(content)
            normalized_title = _normalize_match(title)

            if "/his/department/" in source_url or "/his/contact/" in source_url:
                continue

            score = 0
            if source_url.endswith("/contact"):
                score += 120
            if "/page/2/gioi-thieu-chung" in source_url:
                score += 60
            if "/page/4/co-so-vat-chat" in source_url:
                score += 70
            if "/page/6/so-do-benh-vien" in source_url:
                score += 50
            if any(token in normalized_title for token in ("lien he", "gioi thieu chung", "co so vat chat", "so do benh vien")):
                score += 25
            if "benh vien a" in normalized_content:
                score += 10
            if address_query and any(token in normalized_content for token in ("dia chi", "quang trung", "thinh dan", "quyet thang")):
                score += 40
            if phone_query and any(token in normalized_content for token in ("dien thoai", "hotline", "0280", "0208")):
                score += 35
            if email_query and "gmail" in normalized_content:
                score += 35
            for token in normalized_question.split():
                if token and token in normalized_content:
                    score += 1
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._build_manifest_doc(item) for _, item in scored[:limit]]

    def _dedupe_docs(self, docs: list[Document]) -> list[Document]:
        deduped: list[Document] = []
        seen: set[str] = set()
        for doc in docs:
            chunk_id = str((doc.metadata or {}).get("chunk_id", ""))
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            deduped.append(doc)
        return deduped

    def _extract_phone_numbers(self, docs: list[Document]) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for doc in docs:
            for match in re.finditer(r"(?:\+84|0)[0-9.\-\s()]{8,18}\d", doc.page_content):
                raw = match.group(0)
                digits = re.sub(r"\D", "", raw)
                if digits.startswith("84") and len(digits) == 11:
                    digits = "0" + digits[2:]
                if 10 <= len(digits) <= 11 and digits not in seen:
                    seen.add(digits)
                    results.append(digits)
        return results

    def _extract_emails(self, docs: list[Document]) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()
        for doc in docs:
            for match in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", doc.page_content):
                email = match.group(0).lower()
                if email not in seen:
                    seen.add(email)
                    results.append(email)
        return results

    def _extract_address_candidates(self, docs: list[Document]) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for doc in docs:
            lines = [line.strip(" -") for line in doc.page_content.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                normalized = _normalize_match(line)
                address = ""
                if "address:" in normalized:
                    address = line.split(":", 1)[1].strip()
                elif normalized == "dia chi" and index + 1 < len(lines):
                    address = lines[index + 1].strip()
                elif "duong quang trung" in normalized and "thai nguyen" in normalized:
                    address = line
                elif "thinh dan" in normalized and "thai nguyen" in normalized:
                    address = line
                elif "quyet thang" in normalized and "thai nguyen" in normalized:
                    address = line

                if not address:
                    continue
                cleaned = re.sub(r"^(address:|dia chi:)\s*", "", address, flags=re.IGNORECASE).strip(" -")
                normalized_cleaned = _normalize_match(cleaned)
                if cleaned and normalized_cleaned not in seen:
                    seen.add(normalized_cleaned)
                    candidates.append(cleaned)
        return candidates

    def _structured_hospital_profile_answer(self, question: str, docs: list[Document]) -> AnswerResult | None:
        if not self._is_hospital_level_query(question):
            return None

        context_docs = self._hospital_profile_candidates(question, limit=4)
        if not context_docs:
            return None

        context_docs = self._dedupe_docs(context_docs + docs)
        context_docs = [
            doc
            for doc in context_docs
            if "/his/department/" not in str((doc.metadata or {}).get("source_url", ""))
        ]
        _, sources = self._format_sources(context_docs[:4])

        if self._is_email_query(question):
            emails = self._extract_emails(context_docs)
            if emails:
                answer = f"Email liên hệ của Bệnh viện A Thái Nguyên là {emails[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if self._is_phone_query(question):
            phone_numbers = self._extract_phone_numbers(context_docs)
            if phone_numbers:
                answer = "Bệnh viện A Thái Nguyên có số điện thoại liên hệ là " + " và ".join(phone_numbers[:2]) + " [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if self._is_address_query(question):
            addresses = self._extract_address_candidates(context_docs)
            thinh_dan = [addr for addr in addresses if "thinh dan" in _normalize_match(addr)]
            quyet_thang = [addr for addr in addresses if "quyet thang" in _normalize_match(addr)]
            if thinh_dan and quyet_thang:
                answer = (
                    "Cơ sở tri thức hiện có địa chỉ của Bệnh viện A Thái Nguyên trên đường Quang Trung, thành phố Thái Nguyên. "
                    f"Nguồn đang ghi theo hai cách: \"{thinh_dan[0]}\" và \"{quyet_thang[0]}\" [Nguon 1][Nguon 2]."
                )
                return AnswerResult(question=question, answer=answer, sources=sources[:2])
            if addresses:
                answer = f"Địa chỉ của Bệnh viện A Thái Nguyên là {addresses[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        return None

    def _is_bed_day_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return ("ngay giuong" in normalized or "giuong benh" in normalized) and "benh vien" in normalized

    def _bed_day_tables(self) -> list[dict]:
        tables: list[dict] = []
        for raw in self.kb_tables:
            columns = " ".join(_normalize_match(str(column)) for column in raw.get("columns", []))
            if "ngay giuong" in columns and "don vi" in columns:
                tables.append(raw)
        return tables

    def _bed_day_facility_name(self, question: str) -> str:
        normalized = _normalize_match(question)
        candidates = [
            "Bệnh viện A",
            "Bệnh viện C",
            "Bệnh viện Gang Thép",
            "Bệnh viện Phổi",
            "Bệnh viện Mắt",
            "Bệnh viện Phục hồi chức năng",
            "Bệnh viện Y học cổ truyền",
        ]
        for candidate in candidates:
            if _normalize_match(candidate) in normalized:
                return candidate
        return "Bệnh viện A"

    def _bed_day_matrix_record(self, facility_name: str) -> tuple[dict, dict] | None:
        normalized_facility = _normalize_match(facility_name)
        for table in self._bed_day_tables():
            for row in table.get("rows", []):
                unit = str(row.get("Đơn vị", "")).strip()
                if not unit:
                    continue
                if _normalize_match(unit) == normalized_facility:
                    return table, row
        return None

    def _bed_day_specific_field(self, question: str, row: dict) -> tuple[str, str] | None:
        normalized = _normalize_match(question)
        field_map = [
            ("hoi suc tich cuc", "Ngày điều\ntrị Hồi\nsức tích\ncực\n(ICU)/\nghép\ntạng/ghép\ntủy /ghép\ntế bào gốc", "Ngày điều trị hồi sức tích cực (ICU)/ghép tạng/ghép tủy/ghép tế bào gốc"),
            ("icu", "Ngày điều\ntrị Hồi\nsức tích\ncực\n(ICU)/\nghép\ntạng/ghép\ntủy /ghép\ntế bào gốc", "Ngày điều trị hồi sức tích cực (ICU)/ghép tạng/ghép tủy/ghép tế bào gốc"),
            ("hoi suc cap cuu", "Ngày\ngiường\nbệnh Hồi\nsức cấp\ncứu", "Ngày giường bệnh hồi sức cấp cứu"),
            ("noi khoa loai 1", "Ngày giường bệnh Nội khoa:", "Ngày giường bệnh nội khoa loại 1"),
            ("noi khoa loai 2", "col_6", "Ngày giường bệnh nội khoa loại 2"),
            ("noi khoa loai 3", "col_7", "Ngày giường bệnh nội khoa loại 3"),
            ("ngoai khoa loai 1", "Ngày giường bệnh ngoại khoa, bỏng;", "Ngày giường bệnh ngoại khoa, bỏng loại 1"),
            ("ngoai khoa loai 2", "col_9", "Ngày giường bệnh ngoại khoa, bỏng loại 2"),
            ("ngoai khoa loai 3", "col_10", "Ngày giường bệnh ngoại khoa, bỏng loại 3"),
            ("ngoai khoa loai 4", "col_11", "Ngày giường bệnh ngoại khoa, bỏng loại 4"),
            ("dieu tri ban ngay", "Ngày giường điều trị ban ngày", "Ngày giường điều trị ban ngày"),
            ("ban ngay", "Ngày giường điều trị ban ngày", "Ngày giường điều trị ban ngày"),
        ]
        for marker, key, label in field_map:
            if marker in normalized:
                value = str(row.get(key, "")).strip()
                if value:
                    return label, value
        return None

    def _structured_bed_day_answer(self, question: str) -> AnswerResult | None:
        if not self._is_bed_day_query(question):
            return None

        facility_name = self._bed_day_facility_name(question)
        matched = self._bed_day_matrix_record(facility_name)
        if matched is None:
            return None

        table, row = matched
        title = str(table.get("title") or "Bảng giá ngày giường bệnh")
        source_url = str(table.get("source_url") or "")
        table_id = str(table.get("table_id") or "")
        source = RetrievedSource(
            source_id="Nguon 1",
            title=title,
            locator=source_url or title,
            source_url=source_url or None,
            origin_path=None,
            record_type="table",
            chunk_id=table_id or "bed-day-table",
        )

        specific_field = self._bed_day_specific_field(question, row)
        if specific_field is not None:
            label, value = specific_field
            if "0,3 lần giá ngày" in value:
                answer = f"{label} tại {facility_name} được tính bằng 0,3 lần giá ngày giường của khoa và loại phòng tương ứng [Nguon 1]."
            else:
                answer = f"{label} tại {facility_name} là {value} VNĐ [Nguon 1]."
            return AnswerResult(question=question, answer=answer, sources=[source])

        icu_price = str(row.get("Ngày điều\ntrị Hồi\nsức tích\ncực\n(ICU)/\nghép\ntạng/ghép\ntủy /ghép\ntế bào gốc", "")).strip()
        emergency_price = str(row.get("Ngày\ngiường\nbệnh Hồi\nsức cấp\ncứu", "")).strip()
        answer = (
            f"Giá ngày giường bệnh tại {facility_name} có nhiều mức tùy loại giường [Nguon 1]: "
            f"hồi sức tích cực ICU {icu_price} VNĐ; "
            f"hồi sức cấp cứu {emergency_price} VNĐ; "
            f"nội khoa loại 1 {row.get('Ngày giường bệnh Nội khoa:', '')} VNĐ; "
            f"nội khoa loại 2 {row.get('col_6', '')} VNĐ; "
            f"nội khoa loại 3 {row.get('col_7', '')} VNĐ; "
            f"ngoại khoa, bỏng loại 1 {row.get('Ngày giường bệnh ngoại khoa, bỏng;', '')} VNĐ; "
            f"ngoại khoa, bỏng loại 2 {row.get('col_9', '')} VNĐ; "
            f"ngoại khoa, bỏng loại 3 {row.get('col_10', '')} VNĐ; "
            f"ngoại khoa, bỏng loại 4 {row.get('col_11', '')} VNĐ. "
            f"Ngày giường điều trị ban ngày được tính bằng 0,3 lần giá ngày giường của khoa và loại phòng tương ứng [Nguon 1]."
        )
        return AnswerResult(question=question, answer=answer, sources=[source])

    def _is_director_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        return "giam doc" in normalized and "pho giam doc" not in normalized and "phu trach" not in normalized

    def _is_management_team_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        if self._is_phone_query(question) or self._is_email_query(question):
            return False
        return "ban giam doc" in normalized and any(
            marker in normalized for marker in ("gom", "nhung ai", "co ai", "thanh vien", "ban giam doc benh vien")
        )

    def _management_profile_candidates(self, limit: int = 4) -> list[Document]:
        scored: list[tuple[int, dict]] = []
        for item in self.chunk_manifest:
            source_url = str(item.get("source_url", ""))
            title = str(item.get("title", ""))
            content = str(item.get("content", ""))
            normalized_title = _normalize_match(title)
            normalized_content = _normalize_match(content)

            score = 0
            if "/page/10/ban-giam-doc" in source_url:
                score += 140
            if "/page/2/gioi-thieu-chung" in source_url and "ban giam doc" in normalized_content:
                score += 80
            if "ban giam doc" in normalized_title and (
                "/page/10/ban-giam-doc" in source_url or "/page/2/gioi-thieu-chung" in source_url
            ):
                score += 50
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._build_manifest_doc(item) for _, item in scored[:limit]]

    def _extract_person_name(self, line: str) -> str | None:
        candidate = line.strip(" -,:")
        if ":" in candidate and any(
            marker in _normalize_match(candidate.split(":", 1)[0])
            for marker in ("bsck", "bac si", "thay thuoc", "thay thuoc uu tu")
        ):
            candidate = candidate.split(":", 1)[1].strip()
        else:
            candidate = re.split(r"\s+-\s+", candidate, maxsplit=1)[0].strip()

        candidate = re.sub(
            r"^(?:BSCK\s*II|BSCKII|Bs\.?\s*CKII\.?|Bác sĩ chuyên khoa II|Bác sỹ chuyên khoa II|Thầy thuốc ưu tú,\s*bác sĩ chuyên khoa II|Thầy thuốc ưu tú,\s*bác sỹ chuyên khoa II|Thầy thuốc ưu tú,|Bs\.?)[:\s-]*",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip(" -,:")

        normalized_candidate = _normalize_match(candidate)
        if (
            not candidate
            or len(candidate.split()) < 2
            or re.search(r"\d", candidate)
            or any(marker in normalized_candidate for marker in ("gmail", "email", "sdt", "dien thoai"))
            or normalized_candidate in {
                "ban giam doc",
                "tom tat",
                "giam doc benh vien",
                "pho giam doc benh vien",
                "diem tri thuc",
                "thong tin lien he",
            }
            or any(
                phrase in normalized_candidate
                for phrase in (
                    "ban giam doc",
                    "tom tat",
                    "bi thu dang uy",
                    "pho giam doc",
                    "giam doc benh vien",
                    "diem tri thuc",
                    "thong tin lien he",
                )
            )
        ):
            return None
        return candidate

    def _query_terms(self, question: str, stopwords: set[str] | None = None) -> list[str]:
        stopwords = stopwords or set()
        tokens = []
        for token in _normalize_match(question).split():
            normalized = _normalize_noisy_token(token)
            if not normalized or normalized in stopwords:
                continue
            tokens.append(normalized)
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped

    def _director_entries(self, docs: list[Document]) -> list[tuple[str, Document]]:
        entries: list[tuple[str, Document]] = []
        seen: set[tuple[str, str]] = set()
        for doc in docs:
            content = doc.page_content
            regex_patterns = (
                re.compile(r"BSCK\s*II:\s*([^\n]+?)\s*\n[^\n]*Giám đốc Bệnh viện", flags=re.IGNORECASE),
                re.compile(
                    r"(?:Thầy thuốc ưu tú,\s*)?(?:bác sĩ|bác sỹ)\s+chuyên khoa II\s+([^;\n-]+?)\s*-\s*Bí thư Đảng ủy,\s*giám đốc Bệnh viện",
                    flags=re.IGNORECASE,
                ),
            )
            for pattern in regex_patterns:
                for match in pattern.finditer(content):
                    candidate_name = self._extract_person_name(match.group(1))
                    if candidate_name is None:
                        continue
                    chunk_id = str((doc.metadata or {}).get("chunk_id", ""))
                    dedupe_key = (_normalize_match(candidate_name), chunk_id)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    entries.append((candidate_name, doc))

            lines = [line.strip() for line in doc.page_content.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                window = " ".join(lines[index : index + 3])
                normalized_window = _normalize_match(window)
                if "giam doc benh vien" not in normalized_window or "pho giam doc" in normalized_window:
                    continue

                candidate_name = self._extract_person_name(line)
                if candidate_name is None:
                    for back in range(1, 3):
                        if index - back < 0:
                            break
                        candidate_name = self._extract_person_name(lines[index - back])
                        if candidate_name is not None:
                            break

                if candidate_name is None:
                    continue

                chunk_id = str((doc.metadata or {}).get("chunk_id", ""))
                dedupe_key = (_normalize_match(candidate_name), chunk_id)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries.append((candidate_name, doc))
        return entries

    def _structured_director_answer(self, question: str) -> AnswerResult | None:
        if not self._is_director_query(question):
            return None

        docs = self._management_profile_candidates(limit=4)
        if not docs:
            return None

        entries = self._director_entries(docs)
        if not entries:
            return None

        unique_entries: list[tuple[str, Document]] = []
        seen_names: set[str] = set()
        for name, doc in entries:
            normalized_name = _normalize_match(name)
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            unique_entries.append((name, doc))

        if not unique_entries:
            return None

        entry_docs = [doc for _, doc in unique_entries]
        _, sources = self._format_sources(entry_docs)

        if len(unique_entries) == 1:
            director_name, _ = unique_entries[0]
            answer = f"Giám đốc Bệnh viện A Thái Nguyên là {director_name} [Nguon 1]."
            return AnswerResult(question=question, answer=answer, sources=sources[:1])

        first_name, _ = unique_entries[0]
        second_name, _ = unique_entries[1]
        answer = (
            "Cơ sở tri thức hiện có đang ghi chưa thống nhất về Giám đốc Bệnh viện A Thái Nguyên: "
            f"một nguồn ghi {first_name} [Nguon 1], còn một nguồn khác ghi {second_name} [Nguon 2]."
        )
        return AnswerResult(question=question, answer=answer, sources=sources[:2])

    def _management_member_records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        docs = self._management_profile_candidates(limit=2)
        for doc in docs:
            if "/page/10/ban-giam-doc" not in str((doc.metadata or {}).get("source_url", "")):
                continue
            lines = [line.strip() for line in doc.page_content.splitlines() if line.strip()]
            current: dict[str, object] | None = None
            for line in lines:
                name = self._extract_person_name(line)
                if name is not None:
                    current = {"name": name, "role": "", "phones": [], "emails": [], "doc": doc}
                    records.append(current)
                    continue
                if current is None:
                    continue

                normalized = _normalize_match(line)
                if "@" in line:
                    emails = current.setdefault("emails", [])
                    if isinstance(emails, list) and line not in emails:
                        emails.append(line)
                    continue
                if re.fullmatch(r"(?:\+84|0)[0-9.\-\s()]{8,18}\d", line):
                    phones = current.setdefault("phones", [])
                    if isinstance(phones, list) and line not in phones:
                        phones.append(line)
                    continue
                if normalized.startswith("sdt"):
                    phones = current.setdefault("phones", [])
                    phone = line.split(":", 1)[1].strip() if ":" in line else line.strip()
                    if isinstance(phones, list) and phone and phone not in phones:
                        phones.append(phone)
                    continue
                if normalized in {"gmail", "email"}:
                    continue
                if any(marker in normalized for marker in ("giam doc", "bi thu", "chu tich cong doan")):
                    role = str(current.get("role") or "").strip()
                    current["role"] = f"{role} {line}".strip() if role else line
            break
        return records

    def _structured_management_contact_answer(self, question: str) -> AnswerResult | None:
        normalized = _normalize_match(question)
        if not (self._is_phone_query(question) or self._is_email_query(question)):
            return None
        if not any(marker in normalized for marker in ("giam doc", "ban giam doc", "pho giam doc")):
            return None

        records = self._management_member_records()
        if not records:
            return None

        doc = records[0].get("doc")
        if not isinstance(doc, Document):
            return None
        _, sources = self._format_sources([doc])

        if "ban giam doc" in normalized and "giam doc" not in normalized.replace("ban giam doc", ""):
            if self._is_email_query(question):
                emails = [email for record in records for email in list(record.get("emails") or [])]
                if emails:
                    answer = "Email liên hệ của Ban giám đốc Bệnh viện A Thái Nguyên gồm: " + ", ".join(emails) + " [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            if self._is_phone_query(question):
                phones = [phone for record in records for phone in list(record.get("phones") or [])]
                if phones:
                    answer = "Số điện thoại liên hệ của Ban giám đốc Bệnh viện A Thái Nguyên gồm: " + ", ".join(phones) + " [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if "pho giam doc" in normalized:
            deputy_records = [record for record in records if "pho giam doc" in _normalize_match(str(record.get("role") or ""))]
            if not deputy_records:
                return None
            if self._is_email_query(question):
                emails = [email for record in deputy_records for email in list(record.get("emails") or [])]
                if emails:
                    answer = "Email của Phó Giám đốc Bệnh viện A Thái Nguyên là " + " và ".join(emails) + " [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            if self._is_phone_query(question):
                phones = [phone for record in deputy_records for phone in list(record.get("phones") or [])]
                if phones:
                    answer = "Số điện thoại của Phó Giám đốc Bệnh viện A Thái Nguyên là " + " và ".join(phones) + " [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            return None

        director_records = [
            record
            for record in records
            if "giam doc benh vien" in _normalize_match(str(record.get("role") or ""))
            and "pho giam doc" not in _normalize_match(str(record.get("role") or ""))
        ]
        if not director_records:
            return None
        director = director_records[0]
        if self._is_email_query(question):
            emails = list(director.get("emails") or [])
            if emails:
                answer = f"Theo trang Ban Giám Đốc, email của Giám đốc Bệnh viện A Thái Nguyên là {emails[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])
        if self._is_phone_query(question):
            phones = list(director.get("phones") or [])
            if phones:
                answer = f"Theo trang Ban Giám Đốc, số điện thoại của Giám đốc Bệnh viện A Thái Nguyên là {phones[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])
        return None

    def _management_team_entries(self) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        docs = self._management_profile_candidates(limit=2)
        for doc in docs:
            if "/page/10/ban-giam-doc" not in str((doc.metadata or {}).get("source_url", "")):
                continue
            lines = [line.strip() for line in doc.page_content.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                name = self._extract_person_name(line)
                if name is None:
                    continue
                role = ""
                for look_ahead in range(1, 3):
                    if index + look_ahead >= len(lines):
                        break
                    candidate_role = lines[index + look_ahead].strip()
                    normalized_role = _normalize_match(candidate_role)
                    if any(marker in normalized_role for marker in ("giam doc", "bi thu", "chu tich cong doan")):
                        role_parts = [candidate_role]
                        if candidate_role.endswith("-") and index + look_ahead + 1 < len(lines):
                            next_line = lines[index + look_ahead + 1].strip()
                            normalized_next = _normalize_match(next_line)
                            if any(marker in normalized_next for marker in ("giam doc", "bi thu", "chu tich cong doan")):
                                role_parts.append(next_line)
                        role = " ".join(part.strip(" -") for part in role_parts if part).strip()
                        break
                normalized_name = _normalize_match(name)
                if any(normalized_name == _normalize_match(existing_name) for existing_name, _ in entries):
                    continue
                entries.append((name, role))
        return entries

    def _structured_management_team_answer(self, question: str) -> AnswerResult | None:
        if not self._is_management_team_query(question):
            return None
        docs = self._management_profile_candidates(limit=2)
        primary_docs = [doc for doc in docs if "/page/10/ban-giam-doc" in str((doc.metadata or {}).get("source_url", ""))]
        if not primary_docs:
            return None
        entries = self._management_team_entries()
        if not entries:
            return None
        member_lines = []
        for name, role in entries:
            if role:
                member_lines.append(f"{name} - {role}")
            else:
                member_lines.append(name)
        _, sources = self._format_sources(primary_docs[:1])
        answer = "Ban giám đốc Bệnh viện A Thái Nguyên hiện có: " + "; ".join(member_lines) + " [Nguon 1]."
        return AnswerResult(question=question, answer=answer, sources=sources[:1])

    def _department_candidate_groups(self) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for item in self.chunk_manifest:
            metadata = item.get("metadata") or {}
            page_type = str(metadata.get("page_type", ""))
            if page_type not in {"department", "department_contact"}:
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            groups.setdefault(_normalize_match(title), []).append(item)
        return groups

    def _matched_department_docs(self, question: str, limit: int = 6) -> list[Document]:
        normalized_question = _normalize_match(question)
        if not any(marker in normalized_question for marker in ("khoa", "phong", "trung tam", "don nguyen")):
            return []

        stopwords = {
            "benh",
            "vien",
            "a",
            "la",
            "gi",
            "o",
            "dau",
            "so",
            "dien",
            "thoai",
            "hotline",
            "email",
            "lien",
            "he",
            "lam",
            "nhung",
            "co",
            "khong",
            "khoa",
            "phong",
            "trung",
            "tam",
            "don",
            "nguyen",
        }
        query_terms = self._query_terms(question, stopwords=stopwords)
        scored: list[tuple[int, str, list[dict]]] = []
        for normalized_title, items in self._department_candidate_groups().items():
            title_terms = self._query_terms(normalized_title)
            exact_overlap = sum(1 for token in query_terms if token in title_terms)
            fuzzy_overlap = 0
            for token in query_terms:
                best = max((self._token_similarity(token, title_token) for title_token in title_terms), default=0.0)
                if best >= 0.78:
                    fuzzy_overlap += 1
            if exact_overlap == 0 and fuzzy_overlap == 0 and normalized_title not in normalized_question:
                continue
            score = exact_overlap * 20 + fuzzy_overlap * 16
            if normalized_title in normalized_question:
                score += 80
            score += int(SequenceMatcher(None, " ".join(query_terms), " ".join(title_terms)).ratio() * 50)
            if score >= 45:
                scored.append((score, normalized_title, items))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, _, items = scored[0]
        selected_items = []
        for score, _, candidate_items in scored:
            if score < best_score - 25:
                continue
            selected_items.extend(candidate_items)
        if not selected_items:
            selected_items = items

        def sort_key(item: dict) -> int:
            page_type = str((item.get("metadata") or {}).get("page_type", ""))
            if page_type == "department":
                return 0
            if page_type == "department_contact":
                return 1
            return 2

        selected_items.sort(key=sort_key)
        return self._dedupe_docs([self._build_manifest_doc(item) for item in selected_items])[:limit]

    def _extract_department_address_candidates(self, docs: list[Document]) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()
        for doc in docs:
            lines = [line.strip(" -") for line in doc.page_content.splitlines() if line.strip()]
            for index, line in enumerate(lines):
                normalized = _normalize_match(line)
                address = ""
                if normalized in {"dia chi", "dia chi chinh"} and index + 1 < len(lines):
                    next_line = lines[index + 1].strip()
                    if next_line:
                        address = next_line
                        if index + 2 < len(lines) and any(token in _normalize_match(lines[index + 2]) for token in ("nha", "tang")):
                            address = f"{address} {lines[index + 2].strip()}".strip()
                elif normalized.startswith("dia chi") and ":" in line:
                    address = line.split(":", 1)[1].strip()
                elif "tang" in normalized and "nha" in normalized:
                    address = line
                if not address:
                    continue
                cleaned = re.sub(r"^(dia chi|dia chi chinh)\s*:?\s*", "", address, flags=re.IGNORECASE).strip(" -")
                normalized_cleaned = _normalize_match(cleaned)
                if cleaned and normalized_cleaned not in seen:
                    seen.add(normalized_cleaned)
                    candidates.append(cleaned)
        return candidates

    def _structured_department_contact_answer(self, question: str, search_query: str | None = None) -> AnswerResult | None:
        effective_query = search_query or question
        docs = self._matched_department_docs(effective_query, limit=6)
        if not docs:
            return None
        _, sources = self._format_sources(docs[:2])
        title = str((docs[0].metadata or {}).get("title", "Đơn vị"))

        if self._is_phone_query(question):
            phone_numbers = self._extract_phone_numbers(docs)
            if phone_numbers:
                answer = f"Số điện thoại của {title} là " + " và ".join(phone_numbers[:3]) + " [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if self._is_email_query(question):
            emails = self._extract_emails(docs)
            if emails:
                answer = f"Email liên hệ của {title} là " + " và ".join(emails[:2]) + " [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if self._is_address_query(question):
            addresses = self._extract_department_address_candidates(docs)
            if addresses:
                answer = f"{title} nằm tại {addresses[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        return None

    def _vaccine_doc_entries(self) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for item in self.chunk_manifest:
            metadata = item.get("metadata") or {}
            if str(metadata.get("page_type", "")) != "service_page":
                continue
            source_url = str(item.get("source_url", ""))
            if "/vaccines" not in source_url:
                continue
            doc = self._build_manifest_doc(item)
            content = doc.page_content
            vaccine_name_match = re.search(r"Tên Vắc-xin:\s*\n([^\n]+)", content, flags=re.IGNORECASE)
            antigen_match = re.search(r"Kháng nguyên:\s*\n([^\n]+)", content, flags=re.IGNORECASE)
            manufacturer_match = re.search(r"Sản xuất:\s*\n([^\n]+)", content, flags=re.IGNORECASE)
            price_match = re.search(r"Giá tiền \(VNĐ\):\s*\n([0-9.]+)", content, flags=re.IGNORECASE)
            name = vaccine_name_match.group(1).strip() if vaccine_name_match else ""
            process_steps: list[str] = []
            if "Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên" in content:
                tail = content.split("Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên", 1)[1]
                process_steps = [line.strip() for line in tail.splitlines() if line.strip()]
            entries.append(
                {
                    "doc": doc,
                    "source_url": source_url,
                    "name": name,
                    "antigen": antigen_match.group(1).strip() if antigen_match else "",
                    "manufacturer": manufacturer_match.group(1).strip() if manufacturer_match else "",
                    "price": price_match.group(1).strip() if price_match else "",
                    "phones": self._extract_phone_numbers([doc]),
                    "process_steps": process_steps,
                }
            )
        return entries

    def _matched_vaccine_entry(self, question: str) -> dict[str, object] | None:
        normalized_question = _normalize_match(question)
        entries = self._vaccine_doc_entries()
        if not entries:
            return None
        stopwords = {"benh", "vien", "a", "gia", "bao", "nhieu", "tiem", "vac", "xin", "vaccine", "la", "gi", "lien", "he", "so", "nao", "quy", "trinh"}
        query_terms = self._query_terms(question, stopwords=stopwords)
        alias_map = {
            "rota": ["rotarix"],
            "hpv": ["gardasil"],
        }
        expanded_query_terms = list(query_terms)
        for token in query_terms:
            expanded_query_terms.extend(alias_map.get(token, []))
        scored: list[tuple[int, dict[str, object]]] = []
        for entry in entries:
            name = str(entry.get("name") or "")
            if not name:
                continue
            normalized_name = _normalize_match(name)
            name_terms = self._query_terms(name)
            exact_overlap = sum(1 for token in expanded_query_terms if token in name_terms)
            fuzzy_overlap = 0
            for token in expanded_query_terms:
                best = max((self._token_similarity(token, name_token) for name_token in name_terms), default=0.0)
                if best >= 0.78:
                    fuzzy_overlap += 1
            if exact_overlap == 0 and fuzzy_overlap == 0 and normalized_name not in normalized_question:
                continue
            score = exact_overlap * 22 + fuzzy_overlap * 18
            if normalized_name in normalized_question:
                score += 90
            score += int(SequenceMatcher(None, " ".join(expanded_query_terms), " ".join(name_terms)).ratio() * 50)
            if score >= 40:
                scored.append((score, entry))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _is_vaccine_query(self, question: str) -> bool:
        normalized = _normalize_match(question)
        vaccine_markers = (
            "tiem",
            "tiem chung",
            "vac xin",
            "vaccine",
            "gardasil",
            "rotarix",
            "hepabig",
            "ivacflu",
            "vaxigrip",
            "imojev",
            "synflorix",
            "rotateq",
            "infanrix",
            "heberbiovac",
        )
        return any(marker in normalized for marker in vaccine_markers)

    def _structured_vaccine_answer(self, question: str) -> AnswerResult | None:
        normalized = _normalize_match(question)
        if not self._is_vaccine_query(question):
            return None

        entry = self._matched_vaccine_entry(question)
        if entry is not None:
            doc = entry.get("doc")
            if not isinstance(doc, Document):
                return None
            _, sources = self._format_sources([doc])
            vaccine_name = str(entry.get("name") or "Vắc-xin")
            antigen = str(entry.get("antigen") or "")
            manufacturer = str(entry.get("manufacturer") or "")
            price = str(entry.get("price") or "")
            phones = list(entry.get("phones") or [])
            process_steps = list(entry.get("process_steps") or [])

            if self._is_phone_query(question):
                if phones:
                    answer = f"Số điện thoại liên hệ để tư vấn/đặt tiêm {vaccine_name} là {phones[0]} [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            if self._is_price_query(question):
                if price:
                    answer = f"Giá tiêm vắc-xin {vaccine_name} tại Bệnh viện A Thái Nguyên là {price} VNĐ [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            if any(marker in normalized for marker in ("la vaccine gi", "khang nguyen", "la gi", "hang nao", "san xuat")):
                details = []
                if antigen:
                    details.append(f"kháng nguyên {antigen}")
                if manufacturer:
                    details.append(f"sản xuất bởi {manufacturer}")
                if details:
                    answer = f"{vaccine_name} là vắc-xin {', '.join(details)} [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])
            if "quy trinh" in normalized and process_steps:
                answer = "Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên gồm: " + "; ".join(process_steps[:5]) + " [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

            details = []
            if price:
                details.append(f"giá {price} VNĐ")
            if antigen:
                details.append(f"kháng nguyên {antigen}")
            if phones:
                details.append(f"liên hệ {phones[0]}")
            if details:
                answer = f"Thông tin về {vaccine_name}: " + ", ".join(details) + " [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if "quy trinh tiem chung" in normalized:
            process_docs = [
                self._build_manifest_doc(item)
                for item in self.chunk_manifest
                if str(item.get("source_url", "")) == "https://benhvienathainguyen.com.vn/vaccines"
            ]
            if process_docs:
                primary_doc = process_docs[-1]
                _, sources = self._format_sources([primary_doc])
                content = primary_doc.page_content
                if "Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên" in content:
                    tail = content.split("Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên", 1)[1]
                    steps = [line.strip() for line in tail.splitlines() if line.strip()]
                    if steps:
                        answer = "Quy trình tiêm chủng tại Bệnh viện A Thái Nguyên gồm: " + "; ".join(steps[:5]) + " [Nguon 1]."
                        return AnswerResult(question=question, answer=answer, sources=sources[:1])
        return None

    def _is_price_query(self, question: str) -> bool:
        normalized = self._normalize_pricing_query_text(question)
        tokens = [_normalize_noisy_token(token) for token in normalized.split() if _normalize_noisy_token(token)]
        compact = " ".join(tokens)
        if any(phrase in compact for phrase in ("gia dich vu", "chi phi", "bang gia", "vien phi", "don gia")):
            return True
        meaningful_terms = [token for token in tokens if token not in {"gia", "dich", "vu", "chi", "phi", "bao", "nhieu", "mat", "het", "tien"}]
        if "gia" in tokens and meaningful_terms:
            return True
        has_price_marker = any(token in {"gia", "phi", "mat", "het", "tien"} for token in tokens)
        has_quantity_marker = any(self._token_similarity(token, "nhieu") >= 0.72 for token in tokens)
        return has_price_marker and has_quantity_marker

    def _service_base_name(self, value: str) -> str:
        return re.sub(r"\s*\[[^\]]+\]\s*$", "", value).strip()

    def _normalize_pricing_query_text(self, question: str) -> str:
        normalized = _normalize_match(question)
        replacements = (
            (r"\bdo vat\b", "di vat"),
            (r"\bvat la\b", "di vat"),
            (r"\bvat mac ket\b", "di vat"),
            (r"\bvat bi ket\b", "di vat"),
            (r"\bket trong\b", ""),
            (r"\bbi ket\b", ""),
            (r"\bmac ket\b", ""),
            (r"\btong quat\b", "toan dien"),
        )
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _pricing_query_terms(self, question: str) -> list[str]:
        stopwords = {
            "benh",
            "vien",
            "thai",
            "nguyen",
            "gia",
            "dich",
            "vu",
            "cua",
            "o",
            "tai",
            "la",
            "bao",
            "nhieu",
            "mat",
            "het",
            "chi",
            "phi",
            "benhvien",
            "a",
            "cho",
            "toi",
            "xin",
            "hoi",
            "bi",
            "ket",
            "trong",
            "do",
            "vat",
            "tien",
            "nhiu",
            "nhu",
        }
        normalized_question = self._normalize_pricing_query_text(question)
        raw_tokens = [_normalize_noisy_token(token) for token in normalized_question.split()]
        tokens = [token for token in raw_tokens if token and token not in stopwords]
        if "di" in normalized_question and "vat" in normalized_question and "di" not in tokens:
            tokens.append("di")
        if "vat" in normalized_question and "vat" not in tokens:
            tokens.append("vat")
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            deduped.append(token)
        return deduped

    def _service_match_terms(self, value: str) -> list[str]:
        return [
            token
            for token in (_normalize_noisy_token(token) for token in _normalize_match(value).split())
            if token
        ]

    def _pricing_head_terms(self, terms: list[str]) -> list[str]:
        head_terms = {
            "kham",
            "lay",
            "noi",
            "soi",
            "phau",
            "thuat",
            "sieu",
            "am",
            "xet",
            "nghiem",
            "cat",
            "hut",
            "dat",
            "thao",
            "rut",
            "mo",
        }
        return [term for term in terms if term in head_terms]

    def _token_similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        return SequenceMatcher(None, left, right).ratio()

    def _pricing_service_candidates(self, question: str, limit: int = 6) -> list[Document]:
        if self._is_bed_day_query(question):
            return []
        query_terms = self._pricing_query_terms(question)
        phrase = " ".join(query_terms).strip()
        if not query_terms or not phrase:
            return []
        head_terms = self._pricing_head_terms(query_terms)

        scored: list[tuple[int, Document]] = []
        normalized_question = _normalize_match(question)
        wants_noi_soi = "noi soi" in normalized_question
        wants_gay_me = "gay me" in normalized_question
        wants_gay_te = "gay te" in normalized_question
        wants_khong_gay_me = "khong gay me" in normalized_question

        for doc in self.pricing_service_docs:
            metadata = doc.metadata or {}
            service_name = str(metadata.get("service_name") or metadata.get("approved_name") or metadata.get("technical_name") or "")
            if not service_name:
                continue

            normalized_service = _normalize_match(service_name)
            normalized_base = _normalize_match(self._service_base_name(service_name))
            service_terms = self._service_match_terms(service_name)
            if head_terms and not any(
                any(self._token_similarity(head_term, service_term) >= 0.9 for service_term in service_terms)
                for head_term in head_terms
            ):
                continue
            fuzzy_overlap = 0
            exact_overlap = 0
            for token in query_terms:
                best = max((self._token_similarity(token, service_token) for service_token in service_terms), default=0.0)
                if best >= 0.78:
                    fuzzy_overlap += 1
                if token in service_terms:
                    exact_overlap += 1

            if fuzzy_overlap == 0:
                continue

            ratio = fuzzy_overlap / max(len(query_terms), 1)
            if ratio < 0.5 and fuzzy_overlap < 2:
                continue

            score = exact_overlap * 18 + fuzzy_overlap * 16
            if phrase in normalized_base:
                score += 120
            elif phrase in normalized_service:
                score += 95
            if all(any(self._token_similarity(token, service_token) >= 0.78 for service_token in self._service_match_terms(self._service_base_name(service_name))) for token in query_terms):
                score += 70
            elif all(any(self._token_similarity(token, service_token) >= 0.78 for service_token in service_terms) for token in query_terms):
                score += 50
            if normalized_base.startswith(phrase):
                score += 25
            score += int(SequenceMatcher(None, phrase, " ".join(self._service_match_terms(self._service_base_name(service_name)))).ratio() * 80)
            if wants_noi_soi and "noi soi" in normalized_service:
                score += 12
            if not wants_noi_soi and "noi soi" in normalized_service:
                score -= 8
            if wants_gay_me and "gay me" in normalized_service:
                score += 15
            if wants_gay_te and "gay te" in normalized_service:
                score += 15
            if wants_khong_gay_me and "khong gay me" in normalized_service:
                score += 18

            if score >= 45:
                scored.append((score, doc))

        if not scored:
            return []

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_service = str((scored[0][1].metadata or {}).get("service_name", ""))
        top_base = _normalize_match(self._service_base_name(top_service))
        selected = [
            doc
            for score, doc in scored
            if score >= scored[0][0] - 35
            and _normalize_match(self._service_base_name(str((doc.metadata or {}).get("service_name", "")))) == top_base
        ]
        if not selected:
            selected = [doc for _, doc in scored[:limit]]
        return self._dedupe_docs(selected[:limit])

    def _structured_pricing_answer(self, question: str, focus_question: str | None = None) -> AnswerResult | None:
        if not self._is_price_query(question):
            return None

        docs = self._pricing_service_candidates(question, limit=6)
        if not docs:
            return None

        if focus_question:
            normalized_focus = _normalize_match(focus_question)
            if "khong gay me" in normalized_focus:
                focused_docs = [
                    doc for doc in docs if "khong gay me" in _normalize_match(str((doc.metadata or {}).get("service_name", "")))
                ]
                if focused_docs:
                    docs = focused_docs
            elif "gay te" in normalized_focus:
                focused_docs = [
                    doc for doc in docs if "gay te" in _normalize_match(str((doc.metadata or {}).get("service_name", "")))
                ]
                if focused_docs:
                    docs = focused_docs
            elif "gay me" in normalized_focus:
                focused_docs = [
                    doc
                    for doc in docs
                    if "gay me" in _normalize_match(str((doc.metadata or {}).get("service_name", "")))
                    and "khong gay me" not in _normalize_match(str((doc.metadata or {}).get("service_name", "")))
                ]
                if focused_docs:
                    docs = focused_docs

        deduped_docs: list[Document] = []
        seen_pairs: set[tuple[str, str]] = set()
        for doc in docs:
            metadata = doc.metadata or {}
            service_name = str(metadata.get("service_name") or metadata.get("title") or "").strip()
            price = str(metadata.get("price") or "").strip()
            if not service_name or not price:
                continue
            key = (service_name, price)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            deduped_docs.append(doc)

        entries: list[tuple[str, str, int]] = []
        for index, doc in enumerate(deduped_docs, start=1):
            metadata = doc.metadata or {}
            service_name = str(metadata.get("service_name") or metadata.get("title") or "").strip()
            price = str(metadata.get("price") or "").strip()
            if not service_name or not price:
                continue
            entries.append((service_name, price, index))

        if not entries:
            return None

        _, sources = self._format_sources(deduped_docs[: len(entries)])
        if len(entries) == 1:
            service_name, price, _ = entries[0]
            answer = f"Giá dịch vụ \"{service_name}\" là {price} VNĐ [Nguon 1]."
            return AnswerResult(question=question, answer=answer, sources=sources[:1])

        base_name = self._service_base_name(entries[0][0])
        details = "; ".join(
            f"\"{service_name}\" là {price} VNĐ [Nguon {index}]"
            for service_name, price, index in entries
        )
        answer = (
            f"Trong cơ sở tri thức hiện có, dịch vụ \"{base_name}\" có các mức giá sau: {details}."
        )
        return AnswerResult(question=question, answer=answer, sources=sources[: len(entries)])

    def _rrf_merge(self, ranked_lists: list[list[Document]], limit: int) -> list[Document]:
        scores: dict[str, float] = {}
        docs_by_id: dict[str, Document] = {}
        for ranked_docs in ranked_lists:
            for rank, doc in enumerate(ranked_docs, start=1):
                chunk_id = str((doc.metadata or {}).get("chunk_id", ""))
                if not chunk_id:
                    continue
                docs_by_id.setdefault(chunk_id, doc)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (60 + rank))
        ranked_ids = sorted(scores, key=scores.get, reverse=True)
        return [docs_by_id[chunk_id] for chunk_id in ranked_ids[:limit]]

    def _is_pricing_doc(self, doc: Document) -> bool:
        metadata = doc.metadata or {}
        record_type = str(metadata.get("record_type", ""))
        topic_group = str(metadata.get("topic_group", ""))
        source_url = str(metadata.get("source_url", ""))
        title = _normalize_match(str(metadata.get("title", "")))
        return (
            record_type in {"pricing_pdf_service", "pricing_pdf_page", "table"}
            or topic_group == "pricing"
            or "/page/11/bang-gia-vien-phi" in source_url
            or "bang gia vien phi" in title
        )

    def _faq_detail_docs(self, source_url: str, limit: int = 6) -> list[Document]:
        related_items = [
            item
            for item in self.chunk_manifest
            if str(item.get("source_url", "")) == source_url and str((item.get("metadata") or {}).get("topic_group", "")) == "faq"
        ]
        related_items.sort(key=lambda item: str(item.get("chunk_id", "")))
        return [self._build_manifest_doc(item) for item in related_items[:limit]]

    def _matched_faq_docs(self, question: str, limit: int = 6) -> list[Document]:
        stopwords = {"la", "gi", "bao", "nhieu", "hotline", "dien", "thoai", "so", "lien", "he", "nao"}
        query_terms = self._query_terms(question, stopwords=stopwords)
        if not query_terms:
            return []
        scored: list[tuple[int, str]] = []
        seen_urls: set[str] = set()
        for item in self.chunk_manifest:
            metadata = item.get("metadata") or {}
            source_url = str(item.get("source_url", ""))
            if str(metadata.get("topic_group", "")) != "faq" or "/faqs/faq/" not in source_url or source_url in seen_urls:
                continue
            content_terms = self._query_terms(str(item.get("content", "")), stopwords=stopwords)
            exact_overlap = sum(1 for token in query_terms if token in content_terms)
            fuzzy_overlap = 0
            for token in query_terms:
                best = max((self._token_similarity(token, content_token) for content_token in content_terms), default=0.0)
                if best >= 0.78:
                    fuzzy_overlap += 1
            score = exact_overlap * 18 + fuzzy_overlap * 14
            if score >= 35:
                scored.append((score, source_url))
                seen_urls.add(source_url)

        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        return self._faq_detail_docs(scored[0][1], limit=limit)

    def _structured_faq_contact_answer(self, question: str, search_query: str | None = None) -> AnswerResult | None:
        if not (self._is_phone_query(question) or self._is_email_query(question)):
            return None
        normalized = _normalize_match(question)
        effective_query = search_query or question
        if self._is_hospital_level_query(question):
            return None
        if any(marker in normalized for marker in ("ban giam doc", "giam doc", "pho giam doc")):
            return None
        if self._is_vaccine_query(effective_query):
            return None
        matched_department_docs = self._matched_department_docs(effective_query, limit=1)
        if matched_department_docs:
            matched_title = _normalize_match(str((matched_department_docs[0].metadata or {}).get("title", "")))
            if matched_title and matched_title in _normalize_match(effective_query):
                return None
        referential_follow_up = any(
            marker in normalized for marker in (" do ", " nay ", " khoa do", " phong do", " trung tam do", " nguoi do")
        )
        if not referential_follow_up and matched_department_docs:
            return None
        docs = self._matched_faq_docs(effective_query, limit=6)
        if not docs:
            return None
        if self._is_phone_query(question):
            phones = self._extract_phone_numbers(docs)
            if phones:
                _, sources = self._format_sources([docs[0]])
                answer = f"Số điện thoại liên hệ trong thông tin hỏi đáp là {phones[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])
        if self._is_email_query(question):
            emails = self._extract_emails(docs)
            if emails:
                _, sources = self._format_sources([docs[0]])
                answer = f"Email liên hệ trong thông tin hỏi đáp là {emails[0]} [Nguon 1]."
                return AnswerResult(question=question, answer=answer, sources=sources[:1])
        return None

    def _pricing_page_docs(self) -> list[Document]:
        return [
            self._build_manifest_doc(item)
            for item in self.chunk_manifest
            if "/page/11/bang-gia-vien-phi" in str(item.get("source_url", ""))
        ]

    def _facility_price_from_doc(self, doc: Document, facility_name: str) -> str | None:
        facility_pattern = re.escape(facility_name)
        match = re.search(rf"\b(?:1\s+)?{facility_pattern}\s+([0-9.]+)\b", doc.page_content, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _structured_exam_price_answer(self, question: str) -> AnswerResult | None:
        if not self._is_price_query(question):
            return None
        normalized = _normalize_match(question)
        if "ngay giuong" in normalized or "giuong benh" in normalized:
            return None
        if "kham" not in normalized:
            return None

        facility_name = "Bệnh viện A"
        page_docs = self._pricing_page_docs()
        if not page_docs:
            return None

        if "tong quat" in normalized or "gia kham o benh vien a" in normalized or normalized.strip() == "gia kham benh vien a":
            for doc in page_docs:
                if "gia kham benh" not in _normalize_match(doc.page_content):
                    continue
                price = self._facility_price_from_doc(doc, facility_name)
                if price:
                    _, sources = self._format_sources([doc])
                    answer = f"Giá khám bệnh tại {facility_name} là {price} VNĐ [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])

        if any(marker in normalized for marker in ("kham suc khoe", "lao dong", "lai xe", "dinh ky", "xuat khau lao dong")):
            for doc in page_docs:
                normalized_content = _normalize_match(doc.page_content)
                if "kham suc khoe toan dien" not in normalized_content:
                    continue
                price = self._facility_price_from_doc(doc, facility_name)
                if price:
                    _, sources = self._format_sources([doc])
                    answer = f"Giá khám sức khỏe tại {facility_name} là {price} VNĐ [Nguon 1]."
                    return AnswerResult(question=question, answer=answer, sources=sources[:1])

        return None

    def _structured_consult_price_answer(self, question: str) -> AnswerResult | None:
        if not self._is_price_query(question):
            return None
        normalized = _normalize_match(question)
        if "hoi chan" not in normalized:
            return None
        facility_name = "Bệnh viện A"
        for doc in self._pricing_page_docs():
            normalized_content = _normalize_match(doc.page_content)
            if "hoi chan de xac dinh ca benh kho" not in normalized_content:
                continue
            price = self._facility_price_from_doc(doc, facility_name)
            if not price:
                continue
            _, sources = self._format_sources([doc])
            answer = f"Giá hội chẩn để xác định ca bệnh khó tại {facility_name} là {price} VNĐ [Nguon 1]."
            return AnswerResult(question=question, answer=answer, sources=sources[:1])
        return None

    def retrieve(
        self,
        question: str,
        k: int = DEFAULT_RETRIEVAL_K,
        fetch_k: int = DEFAULT_RETRIEVAL_FETCH_K,
        lambda_mult: float = DEFAULT_RETRIEVAL_LAMBDA,
        search_query: str | None = None,
    ) -> list[Document]:
        effective_query = search_query or question
        department_docs = self._matched_department_docs(effective_query, limit=fetch_k)
        if department_docs and not self._is_price_query(question):
            return department_docs[:k]

        if self._is_vaccine_query(effective_query):
            vaccine_entry = self._matched_vaccine_entry(effective_query)
            if vaccine_entry is not None:
                doc = vaccine_entry.get("doc")
                if isinstance(doc, Document):
                    return [doc]

        semantic_retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": fetch_k, "lambda_mult": lambda_mult},
        )
        semantic_docs = semantic_retriever.invoke(effective_query)
        self.keyword_retriever.k = fetch_k
        keyword_docs = self.keyword_retriever.invoke(effective_query)
        ranked_lists = [semantic_docs, keyword_docs]

        if self._is_price_query(question):
            ranked_lists.insert(0, self._pricing_service_candidates(question, limit=fetch_k))

        docs = self._rrf_merge(ranked_lists, limit=fetch_k)
        if self._is_price_query(question):
            pricing_docs = [
                doc
                for doc in docs
                if str((doc.metadata or {}).get("record_type", "")) in {"pricing_pdf_service", "pricing_pdf_page", "table"}
                or str((doc.metadata or {}).get("topic_group", "")) == "pricing"
                or "/page/11/bang-gia-vien-phi" in str((doc.metadata or {}).get("source_url", ""))
            ]
            if pricing_docs:
                docs = pricing_docs
            return docs[:k]
        non_pricing_docs = [doc for doc in docs if not self._is_pricing_doc(doc)]
        if non_pricing_docs:
            docs = non_pricing_docs
        faq_detail_docs = [
            doc
            for doc in docs
            if "/faqs/faq/" in str((doc.metadata or {}).get("source_url", ""))
            and str((doc.metadata or {}).get("topic_group", "")) == "faq"
        ]
        if faq_detail_docs:
            primary_faq = faq_detail_docs[0]
            source_url = str((primary_faq.metadata or {}).get("source_url", ""))
            expanded_docs = self._faq_detail_docs(source_url, limit=fetch_k)
            if expanded_docs:
                return expanded_docs[:k]
        if not self._is_hospital_level_query(question):
            return docs[:k]

        merged = self._hospital_profile_candidates(question, limit=4) + docs
        merged = self._dedupe_docs(merged)
        non_department = [
            doc
            for doc in merged
            if "/his/department/" not in str((doc.metadata or {}).get("source_url", ""))
            and "/his/contact/" not in str((doc.metadata or {}).get("source_url", ""))
        ]
        if non_department:
            return non_department[:k]
        return merged[:k]

    def _format_sources(self, docs: list[Document]) -> tuple[str, list[RetrievedSource]]:
        rendered_blocks: list[str] = []
        sources: list[RetrievedSource] = []
        for index, doc in enumerate(docs, start=1):
            metadata = doc.metadata or {}
            title = metadata.get("title") or metadata.get("file_name") or metadata.get("record_id", "Nguồn")
            page_number = metadata.get("page_number")
            source_url = metadata.get("source_url") or None
            origin_path = metadata.get("origin_path") or None
            locator_parts = []
            if source_url:
                locator_parts.append(source_url)
            elif origin_path:
                locator_parts.append(origin_path)
            if page_number:
                locator_parts.append(f"trang {page_number}")
            locator = " | ".join(locator_parts) if locator_parts else str(title)
            source_id = f"Nguon {index}"
            sources.append(
                RetrievedSource(
                    source_id=source_id,
                    title=str(title),
                    locator=locator,
                    source_url=source_url,
                    origin_path=origin_path,
                    record_type=str(metadata.get("record_type", "")),
                    chunk_id=str(metadata.get("chunk_id", "")),
                )
            )
            rendered_blocks.append(
                "\n".join(
                    [
                        f"[{source_id}]",
                        f"Tiêu đề: {title}",
                        f"Vị trí: {locator}",
                        "Nội dung:",
                        doc.page_content,
                    ]
                )
            )
        return "\n\n".join(rendered_blocks), sources

    def answer(
        self,
        question: str,
        k: int = DEFAULT_RETRIEVAL_K,
        fetch_k: int = DEFAULT_RETRIEVAL_FETCH_K,
        lambda_mult: float = DEFAULT_RETRIEVAL_LAMBDA,
        context_hint: str | None = None,
    ) -> AnswerResult:
        search_query = self._compose_search_query(question, context_hint)
        structured_bed_day = self._structured_bed_day_answer(search_query)
        if structured_bed_day is not None:
            return structured_bed_day

        structured_faq_contact = self._structured_faq_contact_answer(question, search_query=search_query)
        if structured_faq_contact is not None:
            return structured_faq_contact

        structured_department_contact = self._structured_department_contact_answer(question, search_query=search_query)
        if structured_department_contact is not None:
            return structured_department_contact

        structured_vaccine = self._structured_vaccine_answer(search_query)
        if structured_vaccine is not None:
            return structured_vaccine

        structured_management_contact = self._structured_management_contact_answer(search_query)
        if structured_management_contact is not None:
            return structured_management_contact

        structured_management_team = self._structured_management_team_answer(question)
        if structured_management_team is not None:
            return structured_management_team

        structured_director = self._structured_director_answer(question)
        if structured_director is not None:
            return structured_director

        pricing_query = search_query
        pricing_focus = None
        if context_hint and not self._is_price_query(question) and self._is_price_query(context_hint):
            pricing_query = context_hint
            pricing_focus = question

        structured_exam_pricing = self._structured_exam_price_answer(pricing_query)
        if structured_exam_pricing is not None:
            return structured_exam_pricing

        structured_consult_pricing = self._structured_consult_price_answer(pricing_query)
        if structured_consult_pricing is not None:
            return structured_consult_pricing

        structured_pricing = self._structured_pricing_answer(pricing_query, focus_question=pricing_focus)
        if structured_pricing is not None:
            return structured_pricing
        if self._is_price_query(pricing_query):
            return AnswerResult(
                question=question,
                answer="Tôi chưa tìm thấy thông tin phù hợp trong cơ sở tri thức hiện có.",
                sources=[],
            )

        docs = self.retrieve(question, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, search_query=search_query)
        structured = self._structured_hospital_profile_answer(question, docs)
        if structured is not None:
            return structured
        if not docs:
            return AnswerResult(
                question=question,
                answer="Tôi chưa tìm thấy thông tin phù hợp trong cơ sở tri thức hiện có.",
                sources=[],
            )

        context, sources = self._format_sources(docs)
        prompt_question = search_query if context_hint else question
        messages = self.prompt.format_messages(question=prompt_question, context=context)
        response = self.llm.invoke(messages)
        answer = _stringify_content(response.content).strip() or (
            "Tôi chưa tìm thấy thông tin phù hợp trong cơ sở tri thức hiện có."
        )
        cited_indices = {
            int(match)
            for match in re.findall(r"\[Nguon\s+(\d+)\]", answer, flags=re.IGNORECASE)
            if match.isdigit()
        }
        if cited_indices:
            filtered_sources = [
                source
                for source in sources
                if int(source.source_id.split()[-1]) in cited_indices
            ]
        else:
            filtered_sources = sources
        return AnswerResult(question=question, answer=answer, sources=filtered_sources)
