import logging

import pytest

from investory.logging_config import (
    INVESTORY_LOG_HANDLER_MARKER,
    INVESTORY_LOG_FILE_NAME,
    configure_logging,
)


def _clear_investory_handlers() -> None:
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if getattr(handler, INVESTORY_LOG_HANDLER_MARKER, False):
            root_logger.removeHandler(handler)
            handler.close()


def test_configure_logging_writes_to_file(tmp_path):
    try:
        log_file = configure_logging(logs_dir=tmp_path, log_level="INFO")
        logger = logging.getLogger("investory.test")

        logger.info("test log message")
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert log_file == tmp_path / INVESTORY_LOG_FILE_NAME
        assert log_file.exists()
        assert "test log message" in log_file.read_text(encoding="utf-8")
    finally:
        _clear_investory_handlers()


def test_configure_logging_rejects_unknown_level(tmp_path):
    with pytest.raises(ValueError, match="Unsupported log level"):
        configure_logging(logs_dir=tmp_path, log_level="NOPE")
