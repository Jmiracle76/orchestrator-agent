import ipaddress
import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_PATH = BASE_DIR / "logs" / "app.log"
DEFAULT_SESSION_DIR = os.getenv("WEB_SESSION_DIR", "/tmp/orchestrator_sessions")
DEFAULT_SESSION_TTL = 7 * 24 * 60 * 60


def _session_ttl_seconds() -> int:
    raw_value = os.getenv("WEB_SESSION_TTL_SECONDS")
    if raw_value is None:
        return DEFAULT_SESSION_TTL
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_SESSION_TTL
    return parsed if parsed > 0 else DEFAULT_SESSION_TTL


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _allowed_ips() -> set[str]:
    raw_value = os.getenv("WEB_ALLOWED_IPS")
    allowed: set[str] = {"127.0.0.1", "::1"}
    if not raw_value:
        return allowed
    for item in raw_value.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        try:
            parsed = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        allowed.add(str(parsed))
    return allowed


class BaseConfig:
    SECRET_KEY = os.getenv("WEB_SECRET_KEY") or secrets.token_hex(32)
    LOG_LEVEL = logging.INFO
    LOG_FILE = os.getenv("WEB_LOG_FILE", str(DEFAULT_LOG_PATH))
    LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    TEMPLATES_AUTO_RELOAD = False
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = True
    SESSION_FILE_DIR = DEFAULT_SESSION_DIR
    SESSION_FILE_MODE = 0o600
    SESSION_FILE_THRESHOLD = 500
    SESSION_USE_SIGNER = True
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=_session_ttl_seconds())
    SESSION_COOKIE_SECURE = _env_bool("WEB_SESSION_COOKIE_SECURE", False)
    BIND_ADDRESS = os.getenv("WEB_BIND_ADDRESS", "127.0.0.1")
    ALLOWED_IPS = _allowed_ips()
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = _session_ttl_seconds()
    WTF_CSRF_HEADERS = ("X-CSRFToken", "X-CSRF-Token")
    CSRF_COOKIE_NAME = "csrf_token"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    TEMPLATES_AUTO_RELOAD = True
    ENV_NAME = "development"


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV_NAME = "production"
