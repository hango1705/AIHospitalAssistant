from __future__ import annotations

import sys
import unicodedata
import re
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hospital_assistant.assistant import HospitalAssistant
from hospital_assistant.settings import (
    DEFAULT_LLM_MODEL,
    DEFAULT_RETRIEVAL_FETCH_K,
    DEFAULT_RETRIEVAL_K,
    DEFAULT_RETRIEVAL_LAMBDA,
)

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _print_answer(result) -> None:
    typer.echo("\n=== Trả lời ===")
    typer.echo(result.answer)
    typer.echo("\n=== Nguồn truy xuất ===")
    if not result.sources:
        typer.echo("- Không có nguồn phù hợp.")
        return
    for source in result.sources:
        typer.echo(f"- [{source.source_id}] {source.title} | {source.locator} | {source.chunk_id}")


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_follow_up_question(question: str) -> bool:
    normalized = _normalize_text(question)
    tokens = normalized.split()
    referential_phrases = (
        " do ",
        " ay ",
        " nay ",
        " ho la ai",
        " nguoi do",
        " bac si do",
        " khoa do",
        " phong do",
        " trung tam do",
        " nguoi ay",
        " cai do",
        " cai ay",
        " vi vay",
        " the ai",
    )
    if any(phrase in f" {normalized} " for phrase in referential_phrases):
        return True
    if normalized.startswith("con "):
        return True

    explicit_topic_markers = (
        "benh vien",
        "khoa ",
        "phong ",
        "trung tam ",
        "don nguyen ",
        "ban giam doc",
        "quy trinh",
        "vaccine",
        "tiem ",
        "gardasil",
        "rotarix",
        "ivacflu",
        "hepabig",
        "vaxigrip",
        "bao hiem",
        "bhyt",
        "corona",
        "ncov",
        "bang gia",
        "ngay giuong",
    )
    short_follow_up_prefixes = (
        "gia bao nhieu",
        "bao nhieu",
        "o dau",
        "la gi",
        "nhu the nao",
        "co khong",
        "co dieu tri",
        "so dien thoai",
        "dien thoai",
        "hotline",
        "email",
        "lien he",
        "can mang theo gi",
        "hang nao",
    )
    if len(tokens) <= 8 and any(normalized.startswith(prefix) for prefix in short_follow_up_prefixes):
        return not any(marker in normalized for marker in explicit_topic_markers)
    return len(tokens) <= 6 and not any(marker in normalized for marker in explicit_topic_markers)


@app.command()
def main(
    question: str | None = typer.Option(None, "--question"),
    llm_model: str = typer.Option(DEFAULT_LLM_MODEL, "--llm-model"),
    k: int = typer.Option(DEFAULT_RETRIEVAL_K, "--k"),
    fetch_k: int = typer.Option(DEFAULT_RETRIEVAL_FETCH_K, "--fetch-k"),
    lambda_mult: float = typer.Option(DEFAULT_RETRIEVAL_LAMBDA, "--lambda-mult"),
) -> None:
    _ensure_utf8_stdout()
    assistant = HospitalAssistant(llm_model=llm_model)
    if question:
        _print_answer(assistant.answer(question, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult))
        return

    typer.echo("Hospital assistant đã sẵn sàng. Gõ 'exit' để thoát.")
    topic_anchor: str | None = None
    while True:
        value = input("\nBạn: ").strip()
        if not value:
            continue
        if value.lower() in {"exit", "quit"}:
            break
        context_hint = topic_anchor if topic_anchor and _is_follow_up_question(value) else None
        result = assistant.answer(value, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult, context_hint=context_hint)
        _print_answer(result)
        if not _is_follow_up_question(value):
            topic_anchor = value


if __name__ == "__main__":
    app()
