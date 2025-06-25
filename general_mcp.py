from __future__ import annotations

from fastmcp.server import FastMCP

from research_base import ResearchBase, ResearchConfig


def create_server(config: ResearchConfig | None = None) -> FastMCP:
    base = ResearchBase(config)
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def search(query: str, method: str | None = None):
        """Search records using the given method."""
        results = base.search(query, method=method)
        return {"ids": [r["id"] for r in results]}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch a record by ID."""
        return base.fetch(id)

    return mcp


if __name__ == "__main__":
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
