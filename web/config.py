import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_PATH = BASE_DIR / "logs" / "app.log"


class BaseConfig:
    SECRET_KEY = os.getenv("WEB_SECRET_KEY", "change-me")
    LOG_LEVEL = logging.INFO
    LOG_FILE = os.getenv("WEB_LOG_FILE", str(DEFAULT_LOG_PATH))
    LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    TEMPLATES_AUTO_RELOAD = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    TEMPLATES_AUTO_RELOAD = True
    ENV_NAME = "development"


class ProductionConfig(BaseConfig):
    DEBUG = False
    ENV_NAME = "production"
