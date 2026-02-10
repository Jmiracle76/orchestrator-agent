from __future__ import annotations
import argparse, json, logging, shutil
from pathlib import Path
from dataclasses import asdict
from typing import List
from .models import RunResult
from .config import DEFAULT_DOC_TYPE, SUPPORTED_DOC_TYPES, is_special_workflow_target
from .parsing import extract_metadata, extract_workflow_order, find_sections
from .utils_io import read_text, write_text, split_lines, join_lines, backup_file_outside_repo
from .git_utils import is_working_tree_clean, git_status_porcelain, commit_and_push
from .llm import LLMClient
from .runner import choose_next_target, run_phase

def main(argv: List[str] | None = None) -> int:
    """Run the requirements automation workflow for a single phase pass."""
    parser = argparse.ArgumentParser(description="Requirements automation (phased).")
    parser.add_argument("--template", required=True, help="Template path")
    parser.add_argument("--doc", required=True, help="Requirements doc path")
    parser.add_argument("--repo-root", required=True, help="Repo root path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    # Configure logging once, based on the CLI log-level.
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(levelname)s %(message)s")

    # Normalize paths early so later comparisons are consistent.
    repo_root = Path(args.repo_root).resolve()
    template_path = Path(args.template).resolve()
    doc_path = Path(args.doc).resolve()

    # Avoid committing unrelated changes unless explicitly overridden.
    if not args.no_commit and not is_working_tree_clean(repo_root):
        print("ERROR: Working tree has uncommitted changes.\n")
        print(git_status_porcelain(repo_root))
        return 2

    # If the requirements doc does not exist, seed it from the template.
    if not doc_path.exists():
        if not template_path.exists():
            print(f"ERROR: Template missing: {template_path}")
            return 2
        logging.info("Doc missing; creating from template: %s -> %s", template_path, doc_path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, doc_path)

    # Load document into memory and construct the LLM client.
    lines = split_lines(read_text(doc_path))
    metadata = extract_metadata(lines)
    raw_doc_type = (metadata.get("doc_type") or "").strip()
    doc_type = raw_doc_type.lower() if raw_doc_type else DEFAULT_DOC_TYPE
    if not raw_doc_type:
        logging.warning("No doc_type metadata found; defaulting to %s", DEFAULT_DOC_TYPE)
    if doc_type not in SUPPORTED_DOC_TYPES:
        supported = ", ".join(SUPPORTED_DOC_TYPES)
        logging.error("Unsupported doc_type '%s'. Supported types: %s", doc_type, supported)
        return 2
    llm = LLMClient()

    # Decide which phase is next and execute it.
    try:
        workflow_order = extract_workflow_order(lines)
    except ValueError as e:
        logging.error("Workflow order parse failed: %s", e)
        return 2

    available_section_ids = {sp.section_id for sp in find_sections(lines)}
    invalid_targets = [
        target for target in workflow_order
        if not is_special_workflow_target(target) and target not in available_section_ids
    ]
    if invalid_targets:
        valid = ", ".join(sorted(available_section_ids))
        invalid = ", ".join(invalid_targets)
        logging.error("Workflow order references unknown section IDs: %s", invalid)
        logging.error("Valid section IDs: %s", valid)
        return 2

    target, _ = choose_next_target(lines, workflow_order)
    lines, phase_changed, blocked, _needs_human, _summaries = run_phase(
        target,
        lines,
        llm,
        args.dry_run,
        doc_type=doc_type,
    )

    changed = phase_changed
    outcome = "blocked" if blocked else ("updated" if changed else "no-op")

    # Persist changes, optionally writing a backup first.
    if changed and not args.dry_run:
        backup = backup_file_outside_repo(doc_path)
        logging.info("Backup created: %s", backup)
        write_text(doc_path, join_lines(lines))

    # Commit and push only the target doc, unless --no-commit is set.
    if changed and not args.dry_run and not args.no_commit:
        commit_msg = f"requirements: automation pass ({target})"
        allow = [str(doc_path.relative_to(repo_root)).replace("\\", "/")]
        commit_and_push(repo_root, commit_msg, allow_files=allow)

    # Return a machine-readable summary for callers.
    result = RunResult(outcome=outcome, changed=changed, blocked_reasons=blocked)
    print(json.dumps(asdict(result), indent=2))
    return 0 if outcome in ("no-op", "updated") else 1
