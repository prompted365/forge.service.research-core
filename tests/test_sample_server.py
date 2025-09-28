from __future__ import annotations

from pathlib import Path

import pytest

from fastmcp.server import FastMCP

from sample_mcp import _resolve_records_path, create_server


def test_resolve_records_path_prefers_env(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "alt.json"
    monkeypatch.setenv("CUPCAKE_RECORDS_PATH", str(override))
    resolved = _resolve_records_path(None)
    assert resolved == str(override)


def test_create_server_handles_missing_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CUPCAKE_RECORDS_PATH", raising=False)
    missing = tmp_path / "missing.json"
    server = create_server(records_path=missing)
    assert isinstance(server, FastMCP)


@pytest.mark.asyncio()
async def test_search_returns_empty_when_no_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CUPCAKE_RECORDS_PATH", raising=False)
    missing = tmp_path / "missing.json"
    server = create_server(records_path=missing)
    search_tool = await server.get_tool("search")
    response = await search_tool.fn(query="cupcake")
    assert response == {"ids": []}
