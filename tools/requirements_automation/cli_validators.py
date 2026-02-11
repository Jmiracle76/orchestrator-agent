"""Validation logic for CLI arguments and document structure."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Tuple

from .config import DEFAULT_DOC_TYPE, SUPPORTED_DOC_TYPES, is_special_workflow_target
from .git_utils import git_status_porcelain, is_working_tree_clean
from .parsing import extract_metadata, extract_workflow_order, find_sections


def validate_paths(template_path: Path, doc_path: Path, repo_root: Path) -> Tuple[bool, str]:
    """
    Validate file paths for CLI operation.

    Args:
        template_path: Path to template file
        doc_path: Path to requirements document
        repo_root: Repository root path

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    # Template must exist if doc doesn't exist
    if not doc_path.exists() and not template_path.exists():
        return False, f"ERROR: Template missing: {template_path}"
    return True, ""


def validate_working_tree(repo_root: Path, skip_check: bool = False) -> Tuple[bool, str]:
    """
    Validate that working tree is clean before committing.

    Args:
        repo_root: Repository root path
        skip_check: If True, skip the validation

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if skip_check or is_working_tree_clean(repo_root):
        return True, ""

    status = git_status_porcelain(repo_root)
    return False, f"ERROR: Working tree has uncommitted changes.\n\n{status}"


def validate_doc_type(lines: List[str]) -> Tuple[str, str]:
    """
    Extract and validate document type from metadata.

    Args:
        lines: Document content as list of strings

    Returns:
        Tuple of (doc_type, error_message). error_message is empty if valid.
    """
    metadata = extract_metadata(lines)
    raw_doc_type = (metadata.get("doc_type") or "").strip()
    doc_type = raw_doc_type.lower() if raw_doc_type else DEFAULT_DOC_TYPE

    if not raw_doc_type:
        logging.warning("No doc_type metadata found; defaulting to %s", DEFAULT_DOC_TYPE)

    if doc_type not in SUPPORTED_DOC_TYPES:
        supported = ", ".join(SUPPORTED_DOC_TYPES)
        return doc_type, f"Unsupported doc_type '{doc_type}'. Supported types: {supported}"

    return doc_type, ""


def validate_handler_registry_support(doc_type: str, handler_registry: Any) -> Tuple[bool, str]:
    """
    Validate that handler registry supports the document type.

    Args:
        doc_type: Document type to check
        handler_registry: HandlerRegistry instance

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    if doc_type in handler_registry.config:
        return True, ""

    if "_default" in handler_registry.config:
        logging.warning(
            "doc_type '%s' not explicitly configured in handler registry, "
            "will use default handler configuration",
            doc_type,
        )
        return True, ""

    # No specific config and no default - this is an error
    supported = ", ".join([k for k in handler_registry.config.keys()])
    error_msg = (
        f"doc_type '{doc_type}' not found in handler registry and no _default exists. "
        f"Available types: {supported}"
    )
    return False, error_msg


def validate_workflow_order(lines: List[str]) -> Tuple[List[str], str]:
    """
    Extract and validate workflow order from document.

    Args:
        lines: Document content as list of strings

    Returns:
        Tuple of (workflow_order, error_message). error_message is empty if valid.
    """
    try:
        workflow_order = extract_workflow_order(lines)
    except ValueError as e:
        return [], f"Workflow order parse failed: {e}"

    available_section_ids = {sp.section_id for sp in find_sections(lines)}
    invalid_targets = [
        target
        for target in workflow_order
        if not is_special_workflow_target(target) and target not in available_section_ids
    ]

    if invalid_targets:
        valid = ", ".join(sorted(available_section_ids))
        invalid = ", ".join(invalid_targets)
        error_msg = (
            f"Workflow order references unknown section IDs ({invalid}). "
            f"Valid section IDs: {valid}"
        )
        return workflow_order, error_msg

    return workflow_order, ""
