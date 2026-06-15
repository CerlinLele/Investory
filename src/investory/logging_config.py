"""Logging setup for the Investory application."""

from __future__ import annotations

import logging
from pathlib import Path


INVESTORY_LOG_FILE_NAME = "investory.log"
INVESTORY_LOG_HANDLER_MARKER = "_investory_log_handler"
DEFAULT_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)


def _resolve_log_level(log_level: str) -> int:
    normalized = log_level.strip().upper()
    resolved_level = logging.getLevelName(normalized)
    if isinstance(resolved_level, int):
        return resolved_level
    raise ValueError(f"Unsupported log level: {log_level}")


def configure_logging(*, logs_dir: Path, log_level: str = "INFO") -> Path:
    """Configure console and file logging for Investory."""

    resolved_level = _resolve_log_level(log_level)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / INVESTORY_LOG_FILE_NAME

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    for handler in list(root_logger.handlers):
        if getattr(handler, INVESTORY_LOG_HANDLER_MARKER, False):
            root_logger.removeHandler(handler)
            handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_level)
    console_handler.setFormatter(formatter)
    setattr(console_handler, INVESTORY_LOG_HANDLER_MARKER, True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    setattr(file_handler, INVESTORY_LOG_HANDLER_MARKER, True)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file
