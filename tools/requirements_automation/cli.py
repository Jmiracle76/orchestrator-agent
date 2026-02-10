from __future__ import annotations
import argparse, json, logging, shutil
from pathlib import Path
from dataclasses import asdict
from typing import List
from .models import RunResult
from .utils_io import read_text, write_text, split_lines, join_lines, backup_file_outside_repo
from .git_utils import is_working_tree_clean, git_status_porcelain, commit_and_push
from .llm import LLMClient
from .runner import choose_phase, run_phase

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Requirements automation (phased).")
    parser.add_argument("--template", required=True, help="Template path")
    parser.add_argument("--doc", required=True, help="Requirements doc path")
    parser.add_argument("--repo-root", required=True, help="Repo root path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(levelname)s %(message)s")

    repo_root = Path(args.repo_root).resolve()
    template_path = Path(args.template).resolve()
    doc_path = Path(args.doc).resolve()

    if not args.no_commit and not is_working_tree_clean(repo_root):
        print("ERROR: Working tree has uncommitted changes.\n")
        print(git_status_porcelain(repo_root))
        return 2

    if not doc_path.exists():
        if not template_path.exists():
            print(f"ERROR: Template missing: {template_path}")
            return 2
        logging.info("Doc missing; creating from template: %s -> %s", template_path, doc_path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, doc_path)

    lines = split_lines(read_text(doc_path))
    llm = LLMClient()

    phase, _ = choose_phase(lines)
    lines, phase_changed, blocked, _needs_human, _summaries = run_phase(phase, lines, llm, args.dry_run)

    changed = phase_changed
    outcome = "blocked" if blocked else ("updated" if changed else "no-op")

    if changed and not args.dry_run:
        backup = backup_file_outside_repo(doc_path)
        logging.info("Backup created: %s", backup)
        write_text(doc_path, join_lines(lines))

    if changed and not args.dry_run and not args.no_commit:
        commit_msg = f"requirements: automation pass ({phase})"
        allow = [str(doc_path.relative_to(repo_root)).replace("\\", "/")]
        commit_and_push(repo_root, commit_msg, allow_files=allow)

    result = RunResult(outcome=outcome, changed=changed, blocked_reasons=blocked)
    print(json.dumps(asdict(result), indent=2))
    return 0 if outcome in ("no-op", "updated") else 1
