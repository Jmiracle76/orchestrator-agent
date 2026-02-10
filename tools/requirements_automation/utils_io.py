from __future__ import annotations
import os, shutil, datetime as dt
from pathlib import Path
from typing import List

def iso_today() -> str:
    return dt.date.today().isoformat()

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")

def split_lines(doc: str) -> List[str]:
    return doc.splitlines()

def join_lines(lines: List[str]) -> str:
    return "\n".join(lines) + "\n"

def backup_file_outside_repo(path: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_root = Path(os.getenv("TMPDIR", "/tmp")) / "requirements_automation_backups"
    tmp_root.mkdir(parents=True, exist_ok=True)
    backup_path = tmp_root / f"{path.name}.{ts}.bak"
    shutil.copy2(path, backup_path)
    return backup_path
