from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_base import ResearchBase, ResearchConfig


@pytest.fixture()
def records_file(tmp_path: Path) -> Path:
    payload = [
        {
            "id": "alpha",
            "title": "Alpha project",
            "text": "Testing record",
            "metadata": {"owner": "team-a"},
        },
        {
            "id": "beta",
            "title": "Beta project",
            "text": "",
            "metadata": {"owner": "team-b"},
        },
    ]
    target = tmp_path / "records.json"
    target.write_text(json.dumps(payload))
    return target


def test_missing_records_allowed(tmp_path: Path) -> None:
    config = ResearchConfig(
        records_path=str(tmp_path / "missing.json"), fail_on_missing_records=False
    )
    base = ResearchBase(config)
    assert base.records == []


def test_missing_records_failure(tmp_path: Path) -> None:
    config = ResearchConfig(records_path=str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        ResearchBase(config)


def test_search_and_fetch(records_file: Path) -> None:
    base = ResearchBase(ResearchConfig(records_path=str(records_file)))

    results = base.search("alpha")
    assert [r["id"] for r in results] == ["alpha"]

    with pytest.raises(ValueError):
        base.search("   ")

    with pytest.raises(ValueError):
        base.search("alpha", method=123)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        base.search("alpha", method="   ")

    with pytest.raises(ValueError):
        base.search("alpha", method="unknown")

    with pytest.raises(ValueError):
        base.fetch("   ")

    with pytest.raises(ValueError):
        base.fetch("missing")

    record = base.fetch("alpha")
    assert record["metadata"]["owner"] == "team-a"


def test_long_query_rejected(records_file: Path) -> None:
    base = ResearchBase(ResearchConfig(records_path=str(records_file), max_query_length=10))
    with pytest.raises(ValueError):
        base.search("x" * 11)
