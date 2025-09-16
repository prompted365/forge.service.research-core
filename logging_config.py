"""Logging configuration utilities for MCP servers."""

from __future__ import annotations

import logging
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog-based logging once for the process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=level,
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            _rename_event_key,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def _rename_event_key(_: structlog.types.WrappedLogger, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Rename the default ``event`` key to ``message`` for JSON output."""
    if "event" in event_dict and "message" not in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict
