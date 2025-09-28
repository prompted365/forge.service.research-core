"""Async helpers for talking to MCP research servers from the Reflex UI."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable

import httpx
from fastmcp.client.client import CallToolResult, Client
from fastmcp.exceptions import ToolError

__all__ = [
    "HandshakeMetadata",
    "ToolMetadata",
    "MCPClientError",
    "fetch_handshake",
    "list_tools",
    "search_ids",
    "fetch_record",
    "evaluate_funder",
]


@dataclass(slots=True)
class ToolMetadata:
    """Lightweight description of an MCP tool."""

    name: str
    description: str = ""


@dataclass(slots=True)
class HandshakeMetadata:
    """Structured view over the `/handshake` payload."""

    name: str
    instructions: str
    tools: list[ToolMetadata] = field(default_factory=list)
    endpoints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the metadata into a dictionary for storage in Reflex state."""

        payload = asdict(self)
        payload["tools"] = [asdict(tool) for tool in self.tools]
        return payload


class MCPClientError(RuntimeError):
    """Raised when the MCP client experiences a recoverable failure."""


async def _http_get(base_url: str, path: str, *, timeout: float = 10.0) -> dict:
    """Perform a GET request and return the JSON payload."""

    url = path if path.startswith("http") else f"{base_url.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise MCPClientError("Expected JSON object from MCP endpoint")
        return data


async def fetch_handshake(base_url: str, *, timeout: float = 10.0) -> HandshakeMetadata:
    """Return high-level server metadata for the landing page."""

    data = await _http_get(base_url, "/handshake", timeout=timeout)
    raw_tools = data.get("tools") if isinstance(data, dict) else None
    tools: list[ToolMetadata] = []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                description = str(item.get("description", "")).strip()
                tools.append(ToolMetadata(name=name, description=description))
    instructions = str(data.get("instructions", "")).strip()
    name = str(data.get("name", "Research MCP")).strip() or "Research MCP"
    endpoints = data.get("endpoints") if isinstance(data.get("endpoints"), dict) else {}
    return HandshakeMetadata(name=name, instructions=instructions, tools=tools, endpoints=dict(endpoints))


async def list_tools(base_url: str, *, timeout: float = 10.0) -> list[ToolMetadata]:
    """Fetch the `/list` endpoint as a health check and tool inventory."""

    data = await _http_get(base_url, "/list", timeout=timeout)
    raw_tools = data.get("tools") if isinstance(data, dict) else None
    tools: list[ToolMetadata] = []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                description = str(item.get("description", "")).strip()
                tools.append(ToolMetadata(name=name, description=description))
    return tools


async def _call_tool(base_url: str, tool_name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Invoke a tool using the FastMCP async client."""

    client = Client(base_url)
    try:
        async with client:
            return await client.call_tool(tool_name, arguments)
    except ToolError as exc:  # bubble up user input problems with context
        raise MCPClientError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive failure path
        raise MCPClientError(f"Unable to call tool '{tool_name}': {exc}") from exc


def _normalise_tool_result(result: CallToolResult) -> Any:
    """Reduce FastMCP tool results to plain Python structures."""

    if result.data is not None:
        return result.data
    if result.structured_content:
        return result.structured_content
    if result.content:
        text_blocks = []
        for block in result.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                text_blocks.append(text)
        if text_blocks:
            return "\n".join(text_blocks)
    return None


async def search_ids(base_url: str, query: str, *, method: str | None = None) -> list[str]:
    """Run the `search` tool and return a list of record identifiers."""

    payload: dict[str, Any] = {"query": query}
    if method:
        payload["method"] = method
    result = await _call_tool(base_url, "search", payload)
    data = _normalise_tool_result(result)
    if not isinstance(data, dict):
        raise MCPClientError("Search tool returned unexpected payload")
    raw_ids = data.get("ids")
    if not isinstance(raw_ids, Iterable):
        return []
    clean_ids: list[str] = []
    for value in raw_ids:
        if isinstance(value, str) and value.strip():
            clean_ids.append(value.strip())
    return clean_ids


async def fetch_record(base_url: str, record_id: str) -> dict[str, Any]:
    """Return the raw record payload for the provided identifier."""

    result = await _call_tool(base_url, "fetch", {"id": record_id})
    data = _normalise_tool_result(result)
    if not isinstance(data, dict):
        raise MCPClientError("Fetch tool returned unexpected payload")
    return data


async def evaluate_funder(base_url: str, *, query: str | None = None) -> dict[str, Any]:
    """Trigger the `evaluate` tool used by the funder workflow."""

    payload = {"query": query} if query else {}
    result = await _call_tool(base_url, "evaluate", payload)
    data = _normalise_tool_result(result)
    if isinstance(data, dict):
        return data
    raise MCPClientError("Evaluate tool returned unexpected payload")
