from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

from slugify import slugify

from .config import BASE_URL, BOILERPLATE_PATTERNS


def ensure_dirs(paths: list[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def make_id(prefix: str, raw: str) -> str:
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    return slugify(parsed.path.strip("/")) or "root"


def absolutize(url: str) -> str:
    return urljoin(BASE_URL + "/", url)


def normalize_text(value: str) -> str:
    text = value.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    no_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return no_marks.lower().replace("\u0111", "d").replace("\u0110", "d")


def drop_boilerplate_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        lowered = ascii_fold(line)
        if any(pattern in lowered for pattern in BOILERPLATE_PATTERNS):
            continue
        if len(line) < 2:
            continue
        if line in seen:
            continue
        seen.add(line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
