import os
import stat
import time

import pytest

from web import create_app
from web.session_store import cleanup_expired_sessions


def _build_app(tmp_path, monkeypatch, ttl_seconds: str = "120"):
    monkeypatch.setenv("WEB_SESSION_DIR", str(tmp_path))
    monkeypatch.setenv("WEB_SESSION_TTL_SECONDS", ttl_seconds)
    return create_app("development")


def test_session_configuration_uses_filesystem_dir_and_secure_key(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, ttl_seconds="120")
    assert app.config["SESSION_TYPE"] == "filesystem"
    assert app.config["SESSION_FILE_DIR"] == str(tmp_path)
    assert app.permanent_session_lifetime.total_seconds() == 120

    mode = stat.S_IMODE(os.stat(tmp_path).st_mode)
    assert mode == 0o700
    assert app.secret_key and app.secret_key != "change-me"


def test_workflow_session_persists_across_requests(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    payload = {
        "current_doc": "docs/requirements.md",
        "workflow_params": {"max_steps": 2},
        "execution_history": ["queued", "ran step"],
    }

    first = client.post("/api/session/workflow", json=payload)
    assert first.status_code == 200

    second = client.get("/api/session/workflow")
    data = second.get_json()
    assert data["current_doc"] == payload["current_doc"]
    assert data["workflow_params"] == payload["workflow_params"]
    assert data["execution_history"] == payload["execution_history"]


def test_cleanup_removes_expired_session_files(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, ttl_seconds="1")
    client = app.test_client()

    client.post("/api/session/workflow", json={"current_doc": "docs/requirements.md"})
    session_files = list(tmp_path.iterdir())
    assert session_files

    stale_timestamp = time.time() - 10
    for file_path in session_files:
        os.utime(file_path, (stale_timestamp, stale_timestamp))

    removed = cleanup_expired_sessions(str(tmp_path), app.permanent_session_lifetime)
    assert removed
    assert not any(path.exists() for path in session_files)
