from __future__ import annotations

from web import create_app


def _build_app(tmp_path, monkeypatch, allowed_ips: str | None):
    monkeypatch.setenv("WEB_SESSION_DIR", str(tmp_path))
    if allowed_ips is not None:
        monkeypatch.setenv("WEB_ALLOWED_IPS", allowed_ips)
    return create_app("development")


def test_blocks_non_allowlisted_ip(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, "127.0.0.1")
    client = app.test_client()
    resp = client.get("/", environ_overrides={"REMOTE_ADDR": "203.0.113.5"})
    assert resp.status_code == 403


def test_allows_local_ip_by_default(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, None)
    client = app.test_client()
    resp = client.get("/", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert resp.status_code == 200
