from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hospital_assistant.kb_pipeline import HospitalKnowledgeBaseBuilder
from hospital_assistant.settings import KB_PRICING_PDF_DIR, KNOWLEDGE_BASE_DIR

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


@app.command()
def main(
    knowledge_base_dir: Path = typer.Option(KNOWLEDGE_BASE_DIR, "--knowledge-base-dir"),
    pdf_dir: Path = typer.Option(KB_PRICING_PDF_DIR, "--pdf-dir"),
    pdf_mode: str = typer.Option("elements", "--pdf-mode"),
    pdf_strategy: str = typer.Option("fast", "--pdf-strategy"),
) -> None:
    _ensure_utf8_stdout()
    builder = HospitalKnowledgeBaseBuilder(
        knowledge_base_dir=knowledge_base_dir,
        pdf_dir=pdf_dir,
        pdf_mode=pdf_mode,
        pdf_strategy=pdf_strategy,
    )
    report = builder.build_and_save()
    typer.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
