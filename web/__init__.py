import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask

from web.blueprints.core import core_bp
from web.blueprints.document import document_bp
from web.blueprints.health import health_bp
from web.config import BaseConfig, DevelopmentConfig, ProductionConfig

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    selected_config = _resolve_config(config_name)
    app.config.from_object(selected_config)
    _configure_logging(app)
    _register_blueprints(app)
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
    app.register_blueprint(health_bp)
