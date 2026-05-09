"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


LOGGER_NAME = "market_scanner"


def configure_logging(log_path: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure console and file logging once and return the app logger."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the package logger without changing handler configuration."""

    return logging.getLogger(LOGGER_NAME)
