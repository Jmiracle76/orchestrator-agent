import logging
import os
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from web.blueprints.core import core_bp
from web.blueprints.document import document_api_bp, document_bp
from web.blueprints.health import health_bp
from web.blueprints.session_api import session_api_bp
from web.config import BaseConfig, DevelopmentConfig, ProductionConfig, _session_ttl_seconds
from web.session_store import configure_session

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}

csrf = CSRFProtect()


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    selected_config = _resolve_config(config_name)
    app.config.from_object(selected_config)
    app.config["SESSION_FILE_DIR"] = os.getenv("WEB_SESSION_DIR", app.config["SESSION_FILE_DIR"])
    ttl_seconds = _session_ttl_seconds()
    app.permanent_session_lifetime = timedelta(seconds=ttl_seconds)
    app.config["PERMANENT_SESSION_LIFETIME"] = app.permanent_session_lifetime
    configure_session(app)
    csrf.init_app(app)
    _configure_logging(app)
    _register_blueprints(app)
    _configure_security(app)
    return app


def _resolve_config(config_name: str | None) -> type[BaseConfig]:
    env_name = config_name or os.getenv("WEB_CONFIG") or os.getenv("FLASK_ENV") or "production"
    return CONFIG_MAP.get(env_name.lower(), ProductionConfig)


def _configure_logging(app: Flask) -> None:
    log_level = app.config.get("LOG_LEVEL", logging.INFO)
    log_file = app.config.get("LOG_FILE") or os.path.join(app.root_path, "logs", "app.log")
    log_format = app.config.get(
        "LOG_FORMAT", "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("werkzeug").setLevel(log_level)
    app.logger.handlers = []
    app.logger.propagate = True


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(core_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(document_api_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(session_api_bp)


def _configure_security(app: Flask) -> None:
    allowed_ips = set(app.config.get("ALLOWED_IPS") or ())
    allowed_ips.update({"127.0.0.1", "::1"})

    @app.before_request
    def _enforce_ip_allowlist():
        client_ip = _client_ip()
        if not client_ip:
            return jsonify({"error": "Forbidden", "details": "Unable to determine client address"}), 403
        if allowed_ips and client_ip not in allowed_ips:
            return (
                jsonify({"error": "Forbidden", "details": "Client IP not allowed"}),
                403,
            )

    @app.after_request
    def _set_csrf_cookie(response):
        if request.method in ("GET", "HEAD", "OPTIONS") and response.status_code < 400:
            token = generate_csrf()
            response.headers.setdefault("X-CSRFToken", token)
            response.set_cookie(
                app.config.get("CSRF_COOKIE_NAME", "csrf_token"),
                token,
                secure=bool(app.config.get("SESSION_COOKIE_SECURE")),
                httponly=False,
                samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
                max_age=int(app.permanent_session_lifetime.total_seconds()),
            )
        return response

    @app.errorhandler(CSRFError)
    def _handle_csrf_error(exc: CSRFError):
        return (
            jsonify({"error": "CSRF token missing or invalid", "details": exc.description}),
            400,
        )


def _client_ip() -> str | None:
    if request.access_route:
        return request.access_route[0]
    return request.remote_addr
