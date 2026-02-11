from __future__ import annotations
import argparse, json, logging, shutil
from pathlib import Path
from dataclasses import asdict
from typing import List
from .models import RunResult
from .parsing import extract_metadata
from .utils_io import read_text, write_text, split_lines, join_lines, backup_file_outside_repo
from .git_utils import commit_and_push
from .llm import LLMClient
from .runner_v2 import WorkflowRunner
from .document_validator import DocumentValidator
from .structural_validator import StructuralValidator, report_structural_errors
from .cli_validators import (
    validate_paths, validate_working_tree, validate_doc_type,
    validate_handler_registry_support, validate_workflow_order
)
from .cli_config import load_handler_registry

def main(argv: List[str] | None = None) -> int:
    """Run the requirements automation workflow for a single phase pass."""
    parser = argparse.ArgumentParser(description="Requirements automation (phased).")
    parser.add_argument("--template", required=True, help="Template path")
    parser.add_argument("--doc", required=True, help="Requirements doc path")
    parser.add_argument("--repo-root", required=True, help="Repo root path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--max-steps", type=int, default=1, help="Max workflow steps to execute (default: 1)")
    parser.add_argument("--handler-config", help="Path to handler registry YAML (default: tools/config/handler_registry.yaml)")
    parser.add_argument("--validate", action="store_true", help="Validate document completion without processing")
    parser.add_argument("--strict", action="store_true", help="Enable strict completion checking (includes optional criteria)")
    parser.add_argument("--validate-structure", action="store_true", help="Check document structure without processing")
    args = parser.parse_args(argv)

    # Configure logging once, based on the CLI log-level.
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(levelname)s %(message)s")

    # Normalize paths early so later comparisons are consistent.
    repo_root = Path(args.repo_root).resolve()
    template_path = Path(args.template).resolve()
    doc_path = Path(args.doc).resolve()

    # Load handler registry
    handler_registry, exit_code = load_handler_registry(
        Path(args.handler_config) if args.handler_config else None,
        repo_root
    )
    if exit_code != 0:
        return exit_code

    # Avoid committing unrelated changes unless explicitly overridden.
    # Skip this check for --validate and --validate-structure modes since we're not committing anything
    if not args.validate and not args.validate_structure and not args.no_commit:
        is_valid, error_msg = validate_working_tree(repo_root, skip_check=False)
        if not is_valid:
            print(error_msg)
            return 2

    # Track whether we created a new document from template
    doc_created = False

    # If the requirements doc does not exist, seed it from the template.
    if not doc_path.exists():
        is_valid, error_msg = validate_paths(template_path, doc_path, repo_root)
        if not is_valid:
            print(error_msg)
            return 2
        logging.info("Doc missing; creating from template: %s -> %s", template_path, doc_path)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, doc_path)
        doc_created = True

    # Load document into memory and construct the LLM client.
    lines = split_lines(read_text(doc_path))

    # Handle --validate-structure flag: check structure without processing
    if args.validate_structure:
        # Load template if provided for cross-reference validation
        template_lines = None
        if template_path.exists():
            template_lines = split_lines(read_text(template_path))
        
        validator = StructuralValidator(lines, template_lines)
        errors = validator.validate_all()
        
        # Check if repairs were made
        if validator.repairs_made:
            # Save repaired document
            write_text(doc_path, join_lines(validator.lines))
            print(report_structural_errors(errors, validator.repairs_made))
            return 1  # Non-zero exit to indicate repair was performed
        elif errors:
            print(report_structural_errors(errors))
            return 1
        else:
            print("✅ Document structure valid")
            return 0

    # Fail fast if structure is corrupted
    validator = StructuralValidator(lines)
    errors = validator.validate_all()
    if errors:
        print("ERROR: Document structure validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 2

    metadata = extract_metadata(lines)
    doc_type, error_msg = validate_doc_type(lines)
    if error_msg:
        logging.error(error_msg)
        return 2

    # Validate doc_type is supported by handler registry
    is_valid, error_msg = validate_handler_registry_support(doc_type, handler_registry)
    if not is_valid:
        logging.error(error_msg)
        return 2

    # Decide which phase is next and execute it.
    workflow_order, error_msg = validate_workflow_order(lines)
    if error_msg:
        logging.error(error_msg)
        return 2

    # Handle --validate flag: check completion without processing
    if args.validate:
        validator = DocumentValidator(lines, workflow_order, handler_registry, doc_type)
        status = validator.validate_completion(strict=args.strict)

        # Print human-readable summary
        print(status.summary)
        print()

        # Print machine-readable JSON
        print("JSON Output:")
        print(json.dumps(asdict(status), indent=2))

        return 0 if status.complete else 1

    # Create LLM client only if we're not in validate mode
    llm = LLMClient()

    # Create WorkflowRunner and execute workflow
    runner = WorkflowRunner(lines, llm, doc_type, workflow_order, handler_registry=handler_registry)

    if args.max_steps > 1:
        # Batch execution mode
        results = runner.run_until_blocked(args.dry_run, max_steps=args.max_steps)
        # Use the last result for determining outcome
        last_result = results[-1] if results else None
        if not last_result:
            return 0

        # Update lines from runner (may have been modified)
        lines = runner.lines
        changed = any(r.changed for r in results)
        blocked = last_result.blocked
        blocked_reasons = last_result.blocked_reasons
        target_id = last_result.target_id

        # Log summary of all steps
        for i, result in enumerate(results):
            logging.info("Step %d: target=%s action=%s changed=%s", 
                        i + 1, result.target_id, result.action_taken, result.changed)
    else:
        # Single-step execution mode (default)
        result = runner.run_once(args.dry_run)

        # Update lines from runner (may have been modified)
        lines = runner.lines
        changed = result.changed
        blocked = result.blocked
        blocked_reasons = result.blocked_reasons
        target_id = result.target_id

    outcome = "blocked" if blocked else ("updated" if changed else "no-op")

    # Persist changes, optionally writing a backup first.
    if changed and not args.dry_run:
        backup = backup_file_outside_repo(doc_path)
        logging.info("Backup created: %s", backup)
        write_text(doc_path, join_lines(lines))

    # Commit and push only the target doc, unless --no-commit is set.
    # Commit if either the workflow runner changed content OR we created a new doc from template.
    if (changed or doc_created) and not args.dry_run and not args.no_commit:
        # Use appropriate commit message based on what happened
        if doc_created and not changed:
            commit_msg = "requirements: initialize from template"
        elif doc_created and changed:
            commit_msg = f"requirements: initialize from template and automation pass ({target_id})"
        else:
            commit_msg = f"requirements: automation pass ({target_id})"
        allow = [str(doc_path.relative_to(repo_root)).replace("\\", "/")]
        commit_and_push(repo_root, commit_msg, allow_files=allow)

    # Return a machine-readable summary for callers.
    result = RunResult(outcome=outcome, changed=changed, blocked_reasons=blocked_reasons)
    print(json.dumps(asdict(result), indent=2))
    return 0 if outcome in ("no-op", "updated") else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
