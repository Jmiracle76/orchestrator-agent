from __future__ import annotations

import os
import time
from datetime import timedelta

from flask import Flask
from flask_session import Session


def configure_session(app: Flask) -> Session:
    """Configure server-side session storage and clean up expired entries."""
    session_dir = app.config["SESSION_FILE_DIR"]
    os.makedirs(session_dir, mode=0o700, exist_ok=True)
    os.chmod(session_dir, 0o700)
    cleanup_expired_sessions(session_dir, app.permanent_session_lifetime)
    return Session(app)


def cleanup_expired_sessions(session_dir: str, lifetime: timedelta) -> list[str]:
    removed: list[str] = []
    lifetime_seconds = max(lifetime.total_seconds(), 0)
    if lifetime_seconds <= 0:
        return removed
    if not os.path.isdir(session_dir):
        return removed

    now = time.time()
    for entry in os.scandir(session_dir):
        if not entry.is_file():
            continue
        try:
            age = now - entry.stat().st_mtime
        except FileNotFoundError:
            continue
        if age > lifetime_seconds:
            try:
                os.remove(entry.path)
                removed.append(entry.name)
            except FileNotFoundError:
                continue
    return removed
