from __future__ import annotations

import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bv_a_kb.config import KATANA_DEPTH_BY_MODE
from bv_a_kb.pipeline import BVAKnowledgeBasePipeline

app = typer.Typer(add_completion=False, no_args_is_help=False)


@app.command()
def main(
    mode: str = typer.Option("smoke", "--mode", help="smoke or full"),
    katana_depth: int | None = typer.Option(None, "--katana-depth"),
    crawl_duration: str | None = typer.Option(None, "--crawl-duration"),
) -> None:
    selected_mode = mode.lower().strip()
    if selected_mode not in KATANA_DEPTH_BY_MODE:
        raise typer.BadParameter("mode must be one of: smoke, full")

    pipeline = BVAKnowledgeBasePipeline()
    report = pipeline.run(
        mode=selected_mode,
        katana_depth=katana_depth,
        crawl_duration=crawl_duration,
    )
    typer.echo(report.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
