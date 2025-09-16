"""Input validation helpers for MCP tools."""

from __future__ import annotations

import re
from typing import Optional

from structlog import get_logger

from logging_config import configure_logging

configure_logging()
_logger = get_logger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_METHOD_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class ValidationError(ValueError):
    """Raised when user provided data does not meet expectations."""


def sanitize_query(raw_query: str) -> str:
    """Validate and normalise a search query string."""
    if not isinstance(raw_query, str):
        _logger.warning("invalid_query_type", provided_type=type(raw_query).__name__)
        raise TypeError("query must be provided as a string")

    cleaned = _CONTROL_CHARS.sub(" ", raw_query).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        _logger.warning("empty_query_rejected")
        raise ValidationError("query cannot be empty")
    if len(cleaned) > 512:
        _logger.warning("query_too_long", length=len(cleaned))
        raise ValidationError("query exceeds 512 characters")
    return cleaned


def validate_identifier(raw_identifier: str, *, field: str = "id") -> str:
    """Ensure identifiers are non-empty and match the expected pattern."""
    if not isinstance(raw_identifier, str):
        _logger.warning("invalid_identifier_type", field=field, provided_type=type(raw_identifier).__name__)
        raise TypeError(f"{field} must be provided as a string")

    identifier = raw_identifier.strip()
    if not identifier:
        _logger.warning("empty_identifier_rejected", field=field)
        raise ValidationError(f"{field} cannot be empty")
    if not _IDENTIFIER_RE.fullmatch(identifier):
        _logger.warning("identifier_pattern_mismatch", field=field)
        raise ValidationError(f"{field} may only contain alphanumerics, '_', '.', or '-'")
    return identifier


def normalize_method_name(method: Optional[str]) -> Optional[str]:
    """Sanitise a search method name if provided."""
    if method is None:
        return None
    if not isinstance(method, str):
        _logger.warning("invalid_method_type", provided_type=type(method).__name__)
        raise TypeError("method must be a string when provided")
    candidate = method.strip().lower()
    if not candidate:
        return None
    if not _METHOD_RE.fullmatch(candidate):
        _logger.warning("method_pattern_mismatch", method=method)
        raise ValidationError("method names may only contain alphanumerics, '_', '.', or '-'")
    return candidate
