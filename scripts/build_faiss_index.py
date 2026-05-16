from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hospital_assistant.index_pipeline import HospitalIndexPipeline
from hospital_assistant.settings import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    env_or_default,
    load_env_file,
)

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


@app.command()
def main(
    chunk_size: int = typer.Option(DEFAULT_CHUNK_SIZE, "--chunk-size"),
    chunk_overlap: int = typer.Option(DEFAULT_CHUNK_OVERLAP, "--chunk-overlap"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    reset: bool = typer.Option(False, "--reset"),
) -> None:
    _ensure_utf8_stdout()
    load_env_file()
    if not os.getenv("OPENAI_API_KEY"):
        raise typer.BadParameter("OPENAI_API_KEY not found in environment or .env")

    pipeline = HospitalIndexPipeline()
    report = pipeline.build_index(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model or env_or_default("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        reset=reset,
    )
    typer.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
