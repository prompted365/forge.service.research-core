import pytest

from validators import ValidationError, normalize_method_name, sanitize_query, validate_identifier


def test_sanitize_query_trims_and_collapses_whitespace():
    assert sanitize_query("  Hello   world  ") == "Hello world"


def test_sanitize_query_rejects_empty():
    with pytest.raises(ValidationError):
        sanitize_query("   ")


def test_validate_identifier_allows_safe_chars():
    assert validate_identifier("record-123") == "record-123"


def test_validate_identifier_rejects_bad_chars():
    with pytest.raises(ValidationError):
        validate_identifier("bad id")


def test_normalize_method_name_handles_none():
    assert normalize_method_name(None) is None


def test_normalize_method_name_rejects_invalid():
    with pytest.raises(ValidationError):
        normalize_method_name("invalid name!")
