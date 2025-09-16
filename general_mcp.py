from __future__ import annotations

import structlog
from fastmcp.server import FastMCP

from logging_config import configure_logging
from research_base import ResearchBase, ResearchConfig


configure_logging()
LOGGER = structlog.get_logger("general_mcp")


def create_server(config: ResearchConfig | None = None) -> FastMCP:
    base = ResearchBase(config)
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def search(query: str, method: str | None = None):
        """Search records using the given method."""
        LOGGER.info("search_tool_invoked", query=query, method=method)
        results = base.search(query, method=method)
        ids = [r["id"] for r in results]
        LOGGER.info("search_tool_completed", query=query, method=method, hits=len(ids))
        return {"ids": ids}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch a record by ID."""
        LOGGER.info("fetch_tool_invoked", id=id)
        record = base.fetch(id)
        LOGGER.info("fetch_tool_completed", id=id)
        return record

    return mcp


if __name__ == "__main__":
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
