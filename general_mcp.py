from __future__ import annotations

from fastmcp.server import FastMCP

from logging_utils import get_logger
from research_base import ResearchBase, ResearchConfig

logger = get_logger(__name__)


def create_server(config: ResearchConfig | None = None) -> FastMCP:
    base = ResearchBase(config)
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def search(query: str, method: str | None = None):
        """Search records using the given method."""
        try:
            results = base.search(query, method=method)
        except ValueError as exc:
            logger.warning(
                "tool_search_failed",
                extra={"error": str(exc), "method": method},
            )
            raise
        method_name = (
            method.strip()
            if isinstance(method, str) and method.strip()
            else base.config.default_search
        )
        query_preview = query.strip()[:80] if isinstance(query, str) else ""
        logger.info(
            "tool_search_succeeded",
            extra={
                "method": method_name,
                "query_preview": query_preview,
                "result_count": len(results),
            },
        )
        return {"ids": [r["id"] for r in results if isinstance(r.get("id"), str)]}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch a record by ID."""
        try:
            record = base.fetch(id)
        except ValueError as exc:
            logger.warning(
                "tool_fetch_failed",
                extra={"error": str(exc), "id": id},
            )
            raise
        record_id = record.get("id") if isinstance(record, dict) else None
        resolved_id = (
            record_id.strip() if isinstance(record_id, str) else str(id).strip()
        )
        logger.info(
            "tool_fetch_succeeded",
            extra={"id": resolved_id},
        )
        return record

    return mcp


if __name__ == "__main__":
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
