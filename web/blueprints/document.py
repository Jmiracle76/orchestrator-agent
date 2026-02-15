from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable, Iterable, MutableMapping, Optional

from flask import Blueprint, current_app, jsonify, render_template, request, session

from tools.requirements_automation.cli_config import load_handler_registry
from tools.requirements_automation.cli_validators import (
    validate_doc_type,
    validate_handler_registry_support,
    validate_workflow_order,
)
from tools.requirements_automation.document_validator import DocumentValidator
from tools.requirements_automation.utils_io import read_text, split_lines
from web.cli_wrapper import LogEntry, stream_requirements_cli
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


_STREAM_LOCK = Lock()
_ACTIVE_JOBS: dict[str, "ExecutionJob"] = {}


def _session_id() -> str | None:
    sid = getattr(session, "sid", None)
    if isinstance(sid, str):
        return sid
    fallback = session.get("_id")
    return fallback if isinstance(fallback, str) else None


@dataclass
class ExecutionJob:
    session_id: str
    doc: str
    doc_path: str
    template_path: str
    handler_config: str | None
    params: dict[str, Any]
    started_at: str
    updated_at: str = field(default_factory=_timestamp)
    status: str = "running"
    exit_code: Optional[int] = None
    error: str | None = None
    blocked_reason: str | None = None
    output: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    json_blocks: list[Any] = field(default_factory=list)
    command: list[str] | None = None
    finished_at: str | None = None
    status_message: str = "Workflow execution started"
    persisted: bool = False
    thread: Thread | None = field(default=None, repr=False, compare=False)


def _clear_job(session_id: str | None) -> None:
    if not session_id:
        return
    with _STREAM_LOCK:
        _ACTIVE_JOBS.pop(session_id, None)


def _get_job(session_id: str | None) -> Optional[ExecutionJob]:
    if not session_id:
        return None
    with _STREAM_LOCK:
        return _ACTIVE_JOBS.get(session_id)


def _append_output_line(job: ExecutionJob, line: str, stream_name: str) -> None:
    entry = {"line": line, "stream": stream_name, "timestamp": _timestamp()}
    job.output.append(entry)
    job.updated_at = entry["timestamp"]


def _append_job_log(job: ExecutionJob, log_entry: LogEntry) -> None:
    entry = {
        "level": log_entry.level,
        "message": log_entry.message,
        "stream": log_entry.stream,
        "timestamp": _timestamp(),
    }
    job.logs.append(entry)
    job.updated_at = entry["timestamp"]


def _run_job_for_session(
    job: ExecutionJob,
    repo_root: Path,
    template_path: Path,
    handler_config: Path | None,
) -> None:
    def on_output(line: str, stream_name: str):
        with _STREAM_LOCK:
            _append_output_line(job, line, stream_name)

    def on_log(log_entry: LogEntry):
        with _STREAM_LOCK:
            _append_job_log(job, log_entry)

    result = stream_requirements_cli(
        repo_root=str(repo_root),
        template=str(template_path),
        doc=job.doc_path,
        dry_run=bool(job.params.get("dry_run")),
        no_commit=bool(job.params.get("no_commit")),
        log_level=str(job.params.get("log_level") or "INFO"),
        max_steps=job.params.get("max_steps"),
        handler_config=str(handler_config) if handler_config else None,
        validate=bool(job.params.get("validate")),
        strict=bool(job.params.get("strict")),
        on_output_line=on_output,
        on_log=on_log,
    )

    with _STREAM_LOCK:
        job.exit_code = result.exit_code
        job.error = result.error
        job.json_blocks = result.json_blocks
        job.command = result.command
        job.finished_at = _timestamp()
        job.updated_at = job.finished_at
        if result.status == "success":
            job.status = "completed"
            job.status_message = "Workflow execution finished"
        elif result.status == "timeout":
            job.status = "blocked"
            job.blocked_reason = result.error or "Execution timed out"
            job.status_message = job.blocked_reason
        else:
            job.status = "failed"
            job.status_message = result.error or "Workflow execution failed"


def _launch_execution_job(
    session_id: str | None,
    repo_root: Path,
    doc_rel: str,
    document_path: Path,
    template_path: Path,
    handler_config: Path | None,
    params: dict[str, Any],
) -> ExecutionJob:
    started_at = _timestamp()
    job = ExecutionJob(
        session_id=session_id or "anonymous",
        doc=doc_rel,
        doc_path=str(document_path),
        template_path=str(template_path),
        handler_config=str(handler_config) if handler_config else None,
        params=params,
        started_at=started_at,
        updated_at=started_at,
    )
    _clear_job(session_id)
    with _STREAM_LOCK:
        _ACTIVE_JOBS[job.session_id] = job
    thread = Thread(
        target=_run_job_for_session,
        args=(job, repo_root, template_path, handler_config),
        daemon=True,
    )
    job.thread = thread
    thread.start()
    return job


def _job_output_slice(job: ExecutionJob, since: int) -> tuple[list[dict[str, Any]], int]:
    start = max(since, 0)
    return list(job.output[start:]), len(job.output)


def _merge_job_active(job: ExecutionJob | None, active: MutableMapping | None) -> MutableMapping | None:
    if not job:
        return active
    base = dict(active) if isinstance(active, MutableMapping) else {}
    base.setdefault("started_at", job.started_at)
    base.update(
        {
            "doc": job.doc,
            "status": job.status,
            "message": job.status_message,
            "blocked_reason": job.blocked_reason,
            "updated_at": job.updated_at,
            "finished_at": job.finished_at,
        }
    )
    return base


def _persist_job_completion(
    job: ExecutionJob | None,
    state: WorkflowState,
    history: list[dict[str, Any]],
    log: list[dict[str, Any]],
    active: MutableMapping | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], MutableMapping | None]:
    with _STREAM_LOCK:
        if not job or job.persisted or job.status == "running":
            return state, history, log, active
        job.persisted = True
        doc = job.doc
        status = job.status
        message = job.status_message
        blocked_reason = job.blocked_reason
        updated_at = job.updated_at
        finished_at = job.finished_at

    active_payload: MutableMapping = dict(active) if isinstance(active, MutableMapping) else {}
    active_payload.update(
        {
            "doc": doc,
            "status": status,
            "message": message,
            "blocked_reason": blocked_reason,
            "updated_at": updated_at,
            "finished_at": finished_at,
        }
    )

    _append_execution_event(
        history,
        log,
        doc=doc,
        status=status,
        message=message,
        blocked_reason=blocked_reason,
    )

    updated = _persist_execution_state(
        history,
        log,
        active_payload,
        current_doc=doc,
        workflow_params=state.get("workflow_params"),
    )
    return (
        updated,
        updated.get("execution_history", history),
        updated.get("execution_log", log),
        updated.get("active_execution"),
    )


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

    session_id = _session_id()
    state, history, log, active = _execution_state()
    doc_rel = _relative_path(document_path, repo_root)
    running_job = _get_job(session_id)
    if _is_execution_active(active) or (running_job and running_job.status == "running"):
        blocked_reason = f"Execution already in progress for {active.get('doc') or doc_rel}" if isinstance(active, MutableMapping) else "Execution already in progress"
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
    merged_params = dict(params) if isinstance(params, MutableMapping) else {}
    incoming_params = payload.get("workflow_params")
    if isinstance(incoming_params, MutableMapping):
        merged_params.update(incoming_params)

    # Explicit config inputs take precedence over stored workflow params.
    if "dry_run" in payload:
        merged_params["dry_run"] = bool(payload.get("dry_run"))
    else:
        merged_params["dry_run"] = bool(merged_params.get("dry_run"))

    if "no_commit" in payload:
        merged_params["no_commit"] = bool(payload.get("no_commit"))
    else:
        merged_params["no_commit"] = bool(merged_params.get("no_commit"))

    if "validate" in payload:
        merged_params["validate"] = bool(payload.get("validate"))
    if "strict" in payload:
        merged_params["strict"] = bool(payload.get("strict"))

    max_steps_val: Optional[int] = None
    if "max_steps" in payload or "max_steps" in merged_params:
        raw_steps = payload.get("max_steps", merged_params.get("max_steps"))
        try:
            max_steps_val = int(raw_steps)
        except (TypeError, ValueError):
            return _json_error("Invalid input", 400, "max_steps must be an integer")
        if max_steps_val < 1:
            return _json_error("Invalid input", 400, "max_steps must be at least 1")
        merged_params["max_steps"] = max_steps_val

    log_level_raw = payload.get("log_level") or merged_params.get("log_level") or "INFO"
    merged_params["log_level"] = str(log_level_raw).upper()

    handler_raw = payload.get("handler_config") or merged_params.get("handler_config")
    handler_config: Path | None = None
    if handler_raw:
        try:
            handler_config = _resolve_path(handler_raw, repo_root, "handler_config")
        except ValueError as e:
            return _json_error("Invalid input", 400, str(e))
        if not handler_config.exists():
            return _json_error("Invalid input", 400, f"{handler_config} is missing")
        merged_params["handler_config"] = _relative_path(handler_config, repo_root)
    else:
        merged_params.pop("handler_config", None)

    template_raw = (
        payload.get("template_path") or merged_params.get("template_path") or "docs/templates/requirements-template.md"
    )
    try:
        template_path = _resolve_path(template_raw, repo_root, "template_path")
    except ValueError as e:
        return _json_error("Invalid input", 400, str(e))
    merged_params["template_path"] = _relative_path(template_path, repo_root)

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

    job = _launch_execution_job(
        session_id,
        repo_root,
        doc_rel,
        document_path,
        template_path,
        handler_config,
        merged_params,
    )

    return jsonify(
        {
            "status": "running",
            "active_execution": _merge_job_active(job, updated.get("active_execution")),
            "execution_history": updated.get("execution_history"),
            "execution_log": updated.get("execution_log"),
            "workflow_params": updated.get("workflow_params"),
            "execution_output": [],
            "output_cursor": 0,
        }
    ), 202


@document_api_bp.get("/status")
def document_status():
    state, history, log, active = _execution_state()
    session_id = _session_id()
    job = _get_job(session_id)

    try:
        output_since = max(int(request.args.get("output_since", 0)), 0)
    except ValueError:
        output_since = 0

    output_slice: list[dict[str, Any]] = []
    output_cursor = 0

    if job:
        with _STREAM_LOCK:
            output_slice, output_cursor = _job_output_slice(job, output_since)
            active = _merge_job_active(job, active)
        state, history, log, active = _persist_job_completion(job, state, history, log, active)

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
            "execution_output": output_slice,
            "output_cursor": output_cursor,
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
