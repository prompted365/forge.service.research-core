"""Centralized structured logging helpers for MCP servers."""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict

_LOG_RECORD_DEFAULTS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Render log records as JSON for easier ingestion downstream."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        base: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _LOG_RECORD_DEFAULTS and not key.startswith("_")
        }
        base.update(extra)
        return json.dumps(base, default=str)


def configure_logging(level: str | None = None) -> None:
    """Initialise structured logging once per process."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_level = level or os.getenv("RESEARCH_LOG_LEVEL", "INFO")
    logging.captureWarnings(True)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(resolved_level.upper())
    root.handlers = [handler]

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger with structured logging configured."""

    configure_logging()
    return logging.getLogger(name)
