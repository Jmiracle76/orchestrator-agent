from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from flask import Blueprint, current_app, jsonify, render_template, request

from tools.requirements_automation.cli_config import load_handler_registry
from tools.requirements_automation.cli_validators import (
    validate_doc_type,
    validate_handler_registry_support,
    validate_workflow_order,
)
from tools.requirements_automation.document_validator import DocumentValidator
from tools.requirements_automation.utils_io import read_text, split_lines
from web.session_state import ensure_workflow_state, update_workflow_state

document_bp = Blueprint("document", __name__, url_prefix="/documents")
document_api_bp = Blueprint("document_api", __name__, url_prefix="/api/document")


@document_bp.route("/")
def list_documents():
    documents = [
        {"name": "requirements.md", "status": "in-progress", "updated_at": datetime.utcnow()},
        {"name": "architecture.md", "status": "review", "updated_at": datetime.utcnow()},
    ]
    return render_template(
        "documents/list.html", documents=documents, title="Documents overview"
    )


def _repo_root() -> Path:
    override = current_app.config.get("REPO_ROOT_OVERRIDE")
    if isinstance(override, (str, Path)):
        return Path(override).resolve()
    return Path(current_app.root_path).resolve().parent


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _resolve_path(raw_value: Any, base: Path, field_name: str) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    cleaned = raw_value.strip()
    if len(cleaned) > 300:
        raise ValueError(f"{field_name} is too long")
    candidate = (base / cleaned).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(f"{field_name} must stay within {base}")
    return candidate


def _json_error(message: str, status_code: int = 400, details: str | None = None):
    payload = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def _ensure_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    return payload


def _append_history(record: dict[str, Any]) -> dict[str, Any]:
    state = ensure_workflow_state()
    history: list[dict[str, Any]] = (
        state["execution_history"] if isinstance(state.get("execution_history"), list) else []
    )
    history.append(record)
    return update_workflow_state({"execution_history": history})


def _serialize_checks(checks: Iterable) -> list[dict[str, Any]]:
    return [asdict(check) for check in checks]


@document_api_bp.post("/create")
def create_document():
    repo_root = _repo_root()
    try:
        payload = _ensure_payload()
        template_path = _resolve_path(payload.get("template_path"), repo_root, "template_path")
        document_path = _resolve_path(payload.get("document_path"), repo_root, "document_path")
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    if not template_path.is_file():
        return _json_error("Template not found", 400, f"{template_path} is missing")

    if document_path.exists():
        return _json_error(
            "Document already exists", 409, f"{_relative_path(document_path, repo_root)} exists"
        )

    document_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, document_path)

    update_workflow_state({"current_doc": _relative_path(document_path, repo_root)})

    return (
        jsonify(
            {
                "status": "created",
                "document": {
                    "path": _relative_path(document_path, repo_root),
                    "template": _relative_path(template_path, repo_root),
                },
            }
        ),
        201,
    )


@document_api_bp.post("/execute")
def execute_document():
    repo_root = _repo_root()
    try:
        payload = _ensure_payload()
        document_path = _resolve_path(payload.get("document_path"), repo_root, "document_path")
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    if not document_path.exists():
        return _json_error("Document not found", 404)

    record = {
        "doc": _relative_path(document_path, repo_root),
        "status": "queued",
        "message": "Workflow execution requested",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    state = _append_history(record)
    update_workflow_state({"current_doc": record["doc"]})

    return jsonify({"status": "queued", "execution_history": state["execution_history"]}), 202


@document_api_bp.get("/status")
def document_status():
    state = ensure_workflow_state()
    return jsonify(
        {
            "current_doc": state.get("current_doc"),
            "workflow_params": state.get("workflow_params", {}),
            "execution_history": state.get("execution_history", []),
        }
    )


@document_api_bp.get("/content")
def document_content():
    repo_root = _repo_root()
    raw_path = request.args.get("path")
    if not raw_path:
        state = ensure_workflow_state()
        raw_path = state.get("current_doc")
    try:
        document_path = _resolve_path(raw_path, repo_root, "path")
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    if not document_path.exists():
        return _json_error("Document not found", 404)

    return jsonify(
        {
            "path": _relative_path(document_path, repo_root),
            "content": document_path.read_text(encoding="utf-8"),
        }
    )


@document_api_bp.post("/validate")
def validate_document():
    repo_root = _repo_root()
    try:
        payload = _ensure_payload()
        document_path = _resolve_path(payload.get("document_path"), repo_root, "document_path")
        strict = bool(payload.get("strict"))
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    if not document_path.exists():
        return _json_error("Document not found", 404)

    lines = split_lines(read_text(document_path))

    doc_type, error_msg = validate_doc_type(lines)
    if error_msg:
        return _json_error("Invalid document type", 400, error_msg)

    handler_registry, exit_code = load_handler_registry(None, repo_root)
    if exit_code != 0 or handler_registry is None:
        return _json_error("Handler registry unavailable", 500)

    supported, error_msg = validate_handler_registry_support(doc_type, handler_registry)
    if not supported:
        return _json_error("Unsupported document type", 400, error_msg)

    workflow_order, error_msg = validate_workflow_order(lines)
    if error_msg:
        return _json_error("Workflow validation failed", 400, error_msg)

    validator = DocumentValidator(lines, workflow_order, handler_registry, doc_type)
    status = validator.validate_completion(strict=strict)

    response = {
        "complete": status.complete,
        "blocking_failures": status.blocking_failures,
        "warnings": status.warnings,
        "checks": _serialize_checks(status.checks),
        "summary": status.summary,
        "doc_type": doc_type,
        "document_path": _relative_path(document_path, repo_root),
    }
    return jsonify(response)
