from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from web import create_app


def _build_client(tmp_path: Path, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEB_SESSION_DIR", str(tmp_path / "sessions"))
    repo_root.mkdir(parents=True, exist_ok=True)
    app = create_app("development")
    app.config["REPO_ROOT_OVERRIDE"] = repo_root
    return app.test_client()


def test_create_document_from_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    template_dir = repo_root / "docs" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "base.md"
    template_path.write_text("template content", encoding="utf-8")

    client = _build_client(tmp_path, repo_root, monkeypatch)

    resp = client.post(
        "/api/document/create",
        json={"template_path": "docs/templates/base.md", "document_path": "docs/output.md"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "created"
    created = repo_root / data["document"]["path"]
    assert created.is_file()
    assert created.read_text(encoding="utf-8") == "template content"


def test_rejects_path_escape_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    template_dir = repo_root / "docs" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "base.md").write_text("content", encoding="utf-8")

    client = _build_client(tmp_path, repo_root, monkeypatch)

    resp = client.post(
        "/api/document/create",
        json={"template_path": "../secret.tpl", "document_path": "docs/out.md"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid input"


def test_execute_and_status_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_path = docs_dir / "doc.md"
    doc_path.write_text("hello", encoding="utf-8")

    client = _build_client(tmp_path, repo_root, monkeypatch)

    exec_resp = client.post("/api/document/execute", json={"document_path": "docs/doc.md"})
    assert exec_resp.status_code == 202
    exec_data = exec_resp.get_json()
    assert exec_data["status"] == "queued"
    assert exec_data["execution_history"]

    status_resp = client.get("/api/document/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["current_doc"] == "docs/doc.md"
    assert status_data["execution_history"]

    content_resp = client.get("/api/document/content", query_string={"path": "docs/doc.md"})
    assert content_resp.status_code == 200
    assert content_resp.get_json()["content"] == "hello"


def test_validate_document_uses_handler_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    source_repo = Path(__file__).resolve().parents[1]

    template_src = source_repo / "docs" / "templates" / "requirements-template.md"
    handler_src = source_repo / "tools" / "config" / "handler_registry.yaml"

    target_template_dir = repo_root / "docs" / "templates"
    target_template_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_src, target_template_dir / "requirements-template.md")

    target_doc = docs_dir / "requirements.md"
    shutil.copy2(template_src, target_doc)

    handler_dir = repo_root / "tools" / "config"
    handler_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(handler_src, handler_dir / "handler_registry.yaml")

    client = _build_client(tmp_path, repo_root, monkeypatch)

    resp = client.post("/api/document/validate", json={"document_path": "docs/requirements.md"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["document_path"] == "docs/requirements.md"
    assert "complete" in data
    assert isinstance(data["checks"], list)
