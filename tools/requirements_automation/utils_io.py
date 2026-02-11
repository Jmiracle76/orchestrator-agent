from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path
from typing import List


def iso_today() -> str:
    """Return today's date in ISO-8601 format (YYYY-MM-DD)."""
    return dt.date.today().isoformat()


def read_text(path: Path) -> str:
    """Read a UTF-8 text file into a string."""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 string to disk."""
    path.write_text(text, encoding="utf-8")


def split_lines(doc: str) -> List[str]:
    """Split a document string into a list of lines without trailing newline."""
    return doc.splitlines()


def join_lines(lines: List[str]) -> str:
    """Join lines into a single string with a trailing newline."""
    return "\n".join(lines) + "\n"


def backup_file_outside_repo(path: Path) -> Path:
    """Copy a file to a temp backup folder for rollback safety."""
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_root = Path(os.getenv("TMPDIR", "/tmp")) / "requirements_automation_backups"
    tmp_root.mkdir(parents=True, exist_ok=True)
    backup_path = tmp_root / f"{path.name}.{ts}.bak"
    shutil.copy2(path, backup_path)
    return backup_path
