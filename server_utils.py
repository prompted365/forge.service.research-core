"""Shared utilities for MCP server setup."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from fastmcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from logging_utils import get_logger

logger = get_logger(__name__)


_HANDSHAKE_PATHS: tuple[str, ...] = ("/handshake", "/mcp/handshake")
_TOOL_LIST_PATHS: tuple[str, ...] = ("/list", "/mcp/list")


def _serialise_tools(tools: Dict[str, Any]) -> List[Dict[str, str]]:
    """Convert registered tools into a JSON-friendly listing."""

    serialised: List[Dict[str, str]] = []
    for name, tool in sorted(tools.items()):
        description = getattr(tool, "description", "") or ""
        clean_description = str(description).strip()
        serialised.append({
            "name": str(name),
            "description": clean_description,
        })
    return serialised


def _register_routes(
    server: FastMCP,
    paths: Iterable[str],
    handler: Any,
    methods: list[str],
) -> None:
    """Attach the handler to each path provided."""

    for path in paths:
        server.custom_route(path, methods=methods)(handler)


def register_metadata_routes(server: FastMCP) -> None:
    """Expose handshake metadata and tool listings for HTTP clients."""

    async def handshake(_: Request) -> JSONResponse:
        tools = await server.get_tools()
        serialised_tools = _serialise_tools(tools)
        payload = {
            "name": server.name,
            "instructions": server.instructions,
            "endpoints": {
                "mcp": "/mcp",
                "list": "/list",
            },
            "tools": serialised_tools,
        }
        logger.info(
            "handshake_served",
            extra={
                "tool_count": len(serialised_tools),
                "server_name": server.name,
            },
        )
        return JSONResponse(payload)

    async def list_tools(_: Request) -> JSONResponse:
        tools = await server.get_tools()
        serialised_tools = _serialise_tools(tools)
        logger.info(
            "tool_list_served",
            extra={
                "tool_count": len(serialised_tools),
                "server_name": server.name,
            },
        )
        return JSONResponse({"tools": serialised_tools})

    _register_routes(server, _HANDSHAKE_PATHS, handshake, ["GET"])
    _register_routes(server, _TOOL_LIST_PATHS, list_tools, ["GET"])
