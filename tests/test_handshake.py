from __future__ import annotations

from starlette.testclient import TestClient

from general_mcp import create_server


def test_handshake_endpoints_include_metadata() -> None:
    server = create_server()
    app = server.http_app()
    client = TestClient(app)

    for path in ("/handshake", "/mcp/handshake"):
        response = client.get(path)
        assert response.status_code == 200

        payload = response.json()
        assert payload["name"] == server.name
        assert payload["instructions"] == server.instructions
        assert payload["endpoints"] == {"mcp": "/mcp", "list": "/list"}

        tool_entries = {tool["name"]: tool for tool in payload["tools"]}
        assert "search" in tool_entries
        assert tool_entries["search"]["description"]


def test_tool_list_endpoints_return_registered_tools() -> None:
    server = create_server()
    app = server.http_app()
    client = TestClient(app)

    for path in ("/list", "/mcp/list"):
        response = client.get(path)
        assert response.status_code == 200

        payload = response.json()
        tool_entries = {tool["name"]: tool for tool in payload["tools"]}
        assert "search" in tool_entries
        assert tool_entries["search"]["description"]
