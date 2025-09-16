import json
from pathlib import Path

import pytest

from research_base import ResearchBase, ResearchConfig
from validators import ValidationError


@pytest.fixture()
def sample_records(tmp_path: Path) -> Path:
    records = [
        {
            "id": "alpha-1",
            "title": "Alpha report",
            "text": "Deep dive on alpha",
            "metadata": {"owner": "alice"},
        },
        {
            "id": "beta-2",
            "title": "Beta findings",
            "text": "Follow up for beta",
            "metadata": {"owner": "bob"},
        },
    ]
    path = tmp_path / "records.json"
    path.write_text(json.dumps(records))
    return path


def test_research_base_loads_records_from_memory(sample_records: Path):
    config = ResearchConfig(records_data=[{"id": "alpha", "text": "hello"}])
    base = ResearchBase(config)
    assert base.fetch("alpha")["text"] == "hello"


def test_search_requires_non_empty_query(sample_records: Path):
    config = ResearchConfig(records_path=str(sample_records))
    base = ResearchBase(config)
    with pytest.raises(ValidationError):
        base.search("   ")


def test_fetch_unknown_identifier_raises(sample_records: Path):
    config = ResearchConfig(records_path=str(sample_records))
    base = ResearchBase(config)
    with pytest.raises(ValidationError):
        base.fetch("unknown")


def test_missing_records_file_logs_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    missing_path = tmp_path / "nope.json"
    config = ResearchConfig(records_path=str(missing_path))
    capsys.readouterr()
    base = ResearchBase(config)
    captured = capsys.readouterr()
    assert base.records == []
    assert "records_file_missing" in captured.out
