from __future__ import annotations

import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, MutableMapping

from flask import Blueprint, current_app, jsonify, render_template, request

from tools.requirements_automation.cli_config import load_handler_registry
from tools.requirements_automation.cli_validators import (
    validate_doc_type,
    validate_handler_registry_support,
    validate_workflow_order,
)
from tools.requirements_automation.document_validator import DocumentValidator
from tools.requirements_automation.utils_io import read_text, split_lines
from web.session_state import WorkflowState, ensure_workflow_state, update_workflow_state

document_bp = Blueprint("document", __name__, url_prefix="/documents")
document_api_bp = Blueprint("document_api", __name__, url_prefix="/api/document")

ACTIVE_STATUSES = {"running", "queued"}
FINAL_STATUSES = {"completed", "failed", "canceled"}
VALID_STATUSES = ACTIVE_STATUSES | FINAL_STATUSES | {"blocked"}


@document_bp.route("/")
def list_documents():
    repo_root = _repo_root()
    state = ensure_workflow_state()
    documents = _discover_documents(repo_root, state)
    defaults = {
        "template_path": "docs/templates/requirements-template.md",
        "document_path": state.get("current_doc") or "docs/requirements.md",
    }
    return render_template(
        "documents/list.html",
        documents=documents,
        workflow_state=state,
        defaults=defaults,
        repo_root=str(repo_root),
        title="Documents overview",
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


def _serialize_checks(checks: Iterable) -> list[dict[str, Any]]:
    return [asdict(check) for check in checks]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _execution_state():
    state = ensure_workflow_state()
    history = state["execution_history"] if isinstance(state.get("execution_history"), list) else []
    log = state["execution_log"] if isinstance(state.get("execution_log"), list) else []
    active = state["active_execution"] if isinstance(state.get("active_execution"), MutableMapping) else None
    return state, history, log, active


def _persist_execution_state(
    history: list[dict[str, Any]],
    log: list[dict[str, Any]],
    active: MutableMapping | None,
    *,
    current_doc: str | None = None,
    workflow_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {
        "execution_history": history,
        "execution_log": log,
        "active_execution": active,
    }
    if current_doc is not None:
        updates["current_doc"] = current_doc
    if isinstance(workflow_params, MutableMapping):
        updates["workflow_params"] = workflow_params
    return update_workflow_state(updates)


def _append_execution_event(
    history: list[dict[str, Any]],
    log: list[dict[str, Any]],
    *,
    doc: str | None,
    status: str,
    message: str,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "doc": doc,
        "status": status,
        "message": message,
        "timestamp": _timestamp(),
    }
    if blocked_reason:
        entry["blocked_reason"] = blocked_reason
    history.append(entry)
    log.append(entry)
    return entry


def _is_execution_active(active: MutableMapping | None) -> bool:
    if not isinstance(active, MutableMapping):
        return False
    status = str(active.get("status") or "").lower()
    return status in ACTIVE_STATUSES


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

    state, history, log, active = _execution_state()
    doc_rel = _relative_path(document_path, repo_root)
    if _is_execution_active(active):
        blocked_reason = f"Execution already in progress for {active.get('doc') or doc_rel}"
        if isinstance(active, MutableMapping):
            active = dict(active)
            active["blocked_reason"] = blocked_reason
            active["updated_at"] = _timestamp()
        _append_execution_event(
            history,
            log,
            doc=doc_rel,
            status="blocked",
            message="Execution blocked",
            blocked_reason=blocked_reason,
        )
        updated = _persist_execution_state(history, log, active)
        return (
            jsonify(
                {
                    "status": "blocked",
                    "blocked_reason": blocked_reason,
                    "active_execution": updated.get("active_execution"),
                    "execution_history": updated.get("execution_history"),
                    "execution_log": updated.get("execution_log"),
                }
            ),
            409,
        )

    params = state.get("workflow_params", {})
    incoming_params = payload.get("workflow_params")
    if isinstance(incoming_params, MutableMapping):
        merged_params = dict(params) if isinstance(params, MutableMapping) else {}
        merged_params.update(incoming_params)
    else:
        merged_params = params if isinstance(params, MutableMapping) else {}

    timestamp = _timestamp()
    active_execution: dict[str, Any] = {
        "doc": doc_rel,
        "status": "running",
        "message": "Workflow execution started",
        "blocked_reason": None,
        "started_at": timestamp,
        "updated_at": timestamp,
    }
    _append_execution_event(
        history, log, doc=doc_rel, status="running", message="Workflow execution started"
    )

    updated = _persist_execution_state(
        history, log, active_execution, current_doc=doc_rel, workflow_params=merged_params
    )

    return jsonify(
        {
            "status": "running",
            "active_execution": updated.get("active_execution"),
            "execution_history": updated.get("execution_history"),
            "execution_log": updated.get("execution_log"),
        }
    ), 202


@document_api_bp.get("/status")
def document_status():
    state, history, log, active = _execution_state()
    since = request.args.get("since")
    filtered_log = log
    if since is not None:
        try:
            start_idx = max(int(since), 0)
        except ValueError:
            start_idx = 0
        filtered_log = log[start_idx:]
    return jsonify(
        {
            "current_doc": state.get("current_doc"),
            "workflow_params": state.get("workflow_params", {}),
            "execution_history": history,
            "execution_log": filtered_log,
            "log_cursor": len(log),
            "active_execution": active,
        }
    )


def _document_status(doc_path: str, state: WorkflowState) -> str:
    active = state.get("active_execution")
    if isinstance(active, MutableMapping):
        if str(active.get("doc")) == doc_path:
            return str(active.get("status") or "running")
    if state.get("current_doc") == doc_path:
        return "ready"
    return "idle"


def _discover_documents(repo_root: Path, state: WorkflowState) -> list[dict[str, Any]]:
    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        return []

    documents: list[dict[str, Any]] = []
    for path in docs_dir.rglob("*.md"):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        relative = _relative_path(path, repo_root)
        updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        documents.append(
            {
                "name": relative,
                "status": _document_status(relative, state),
                "updated_at": updated_at,
                "updated_at_iso": updated_at.isoformat(),
            }
        )

    documents.sort(key=lambda item: item["updated_at"], reverse=True)
    return documents


@document_api_bp.post("/execute/status")
def update_execution_status():
    repo_root = _repo_root()
    try:
        payload = _ensure_payload()
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    raw_status = payload.get("status")
    if not isinstance(raw_status, str) or not raw_status.strip():
        return _json_error("Invalid input", 400, "Execution status is required")
    status = raw_status.strip().lower()
    if status not in VALID_STATUSES:
        return _json_error("Invalid input", 400, "Unsupported execution status")

    message = payload.get("message") or "Status updated"
    blocked_reason = payload.get("blocked_reason")
    raw_doc = payload.get("document_path")
    state, history, log, active = _execution_state()

    resolved_doc: str | None = None
    doc_source = raw_doc or state.get("current_doc")
    if doc_source:
        try:
            resolved_doc = _relative_path(
                _resolve_path(doc_source, repo_root, "document_path"), repo_root
            )
        except ValueError as e:
            return _json_error("Invalid input", 400, str(e))

    timestamp = _timestamp()
    _append_execution_event(
        history,
        log,
        doc=resolved_doc,
        status=status,
        message=message,
        blocked_reason=blocked_reason,
    )

    next_active = dict(active) if isinstance(active, MutableMapping) else {}
    if resolved_doc:
        next_active["doc"] = resolved_doc
    next_active["status"] = status
    next_active["message"] = message
    next_active["blocked_reason"] = blocked_reason
    next_active["updated_at"] = timestamp
    next_active.setdefault("started_at", timestamp)

    updated = _persist_execution_state(
        history, log, next_active, current_doc=resolved_doc or state.get("current_doc")
    )

    return jsonify(
        {
            "status": status,
            "active_execution": updated.get("active_execution"),
            "execution_log": updated.get("execution_log"),
            "execution_history": updated.get("execution_history"),
            "log_cursor": len(updated.get("execution_log", [])),
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


@document_api_bp.post("/content")
def update_document_content():
    repo_root = _repo_root()
    try:
        payload = _ensure_payload()
        raw_path = payload.get("document_path") or payload.get("path")
        document_path = _resolve_path(raw_path, repo_root, "document_path")
        new_content = payload.get("content")
        if not isinstance(new_content, str):
            raise ValueError("content must be a string")
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))

    if not document_path.exists():
        return _json_error("Document not found", 404)

    document_path.write_text(new_content, encoding="utf-8")
    updated_at = datetime.fromtimestamp(document_path.stat().st_mtime, tz=timezone.utc)
    update_workflow_state({"current_doc": _relative_path(document_path, repo_root)})
    return jsonify(
        {
            "status": "updated",
            "document_path": _relative_path(document_path, repo_root),
            "updated_at": updated_at.isoformat(),
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
