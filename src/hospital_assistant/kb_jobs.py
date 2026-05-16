from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess
import sys

from .settings import ROOT_DIR
from .server_store import AppStore


class KbJobRunner:
    def __init__(self, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def run(self, store: AppStore, job_id: int, reload_assistant: Callable[[], None]) -> None:
        store.update_kb_update_job(job_id, status="running", append_log="Job started.")
        try:
            self._run_command(store, job_id, [sys.executable, "scripts/build_hospital_corpus.py"])
            self._run_command(store, job_id, [sys.executable, "scripts/build_faiss_index.py", "--reset"])
            reload_assistant()
            store.update_kb_update_job(job_id, status="success", append_log="Job completed and assistant cache was reloaded.")
        except Exception as exc:
            store.update_kb_update_job(job_id, status="failed", append_log=f"Job failed: {exc}")

    def _run_command(self, store: AppStore, job_id: int, command: list[str]) -> None:
        store.update_kb_update_job(job_id, append_log=f"Running: {' '.join(command)}")
        completed = subprocess.run(
            command,
            cwd=self.root_dir,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        if output:
            store.update_kb_update_job(job_id, append_log=output[-4000:])
        if completed.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} exited with code {completed.returncode}")
