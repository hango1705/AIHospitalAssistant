from __future__ import annotations

import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hospital_assistant.assistant import HospitalAssistant
from hospital_assistant.settings import DEFAULT_RETRIEVAL_FETCH_K, DEFAULT_RETRIEVAL_K, DEFAULT_RETRIEVAL_LAMBDA

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


@app.command()
def main(
    query: str = typer.Option(..., "--query"),
    k: int = typer.Option(DEFAULT_RETRIEVAL_K, "--k"),
    fetch_k: int = typer.Option(DEFAULT_RETRIEVAL_FETCH_K, "--fetch-k"),
    lambda_mult: float = typer.Option(DEFAULT_RETRIEVAL_LAMBDA, "--lambda-mult"),
    preview_chars: int = typer.Option(420, "--preview-chars"),
) -> None:
    _ensure_utf8_stdout()
    assistant = HospitalAssistant()
    docs = assistant.retrieve(query, k=k, fetch_k=fetch_k, lambda_mult=lambda_mult)
    typer.echo(f"Query: {query}")
    typer.echo(f"Retrieved chunks: {len(docs)}")
    for index, doc in enumerate(docs, start=1):
        metadata = doc.metadata or {}
        preview = doc.page_content[:preview_chars].replace("\n", " ")
        typer.echo("")
        typer.echo(f"[{index}] {metadata.get('title', '')}")
        typer.echo(f"  chunk_id: {metadata.get('chunk_id', '')}")
        typer.echo(f"  source_url: {metadata.get('source_url', '')}")
        typer.echo(f"  origin_path: {metadata.get('origin_path', '')}")
        typer.echo(f"  preview: {preview}")


if __name__ == "__main__":
    app()
