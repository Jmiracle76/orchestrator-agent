#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from requirements_automation.cli import main

if __name__ == "__main__":
    repo_root = HERE.parent
    template = repo_root / "docs" / "templates" / "requirements-template.md"
    doc = repo_root / "docs" / "requirements.md"

    argv = [
        "--repo-root", str(repo_root),
        "--template", str(template),
        "--doc", str(doc),
    ] + sys.argv[1:]

    raise SystemExit(main(argv))
