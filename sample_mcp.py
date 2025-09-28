from __future__ import annotations

import os
from pathlib import Path

from fastmcp.server import FastMCP

from logging_utils import get_logger
from research_base import ResearchBase, ResearchConfig
from server_utils import register_metadata_routes

logger = get_logger(__name__)

_DEFAULT_RECORDS = Path(__file__).with_name("records.json")


def _resolve_records_path(records_path: str | os.PathLike[str] | None) -> str:
    env_override = os.getenv("CUPCAKE_RECORDS_PATH")
    candidate = Path(env_override or records_path or _DEFAULT_RECORDS)
    return str(candidate)


def create_server(records_path: str | os.PathLike[str] | None = None) -> FastMCP:
    config = ResearchConfig(
        name="Cupcake MCP",
        instructions="Search cupcake orders",
        records_path=_resolve_records_path(records_path),
        fail_on_missing_records=False,
    )
    base = ResearchBase(config)
    if not base.records:
        logger.warning(
            "cupcake_records_empty",
            extra={"path": config.records_path},
        )
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def search(query: str):
        """Search for cupcake orders via keyword matching."""
        try:
            results = base.search(query)
        except ValueError as exc:
            logger.warning(
                "cupcake_search_failed", extra={"error": str(exc)}
            )
            raise
        ids = [r["id"] for r in results if isinstance(r.get("id"), str)]
        logger.info(
            "cupcake_search_succeeded",
            extra={"result_count": len(ids)},
        )
        return {"ids": ids}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch a cupcake order by ID."""
        try:
            record = base.fetch(id)
        except ValueError as exc:
            logger.warning(
                "cupcake_fetch_failed",
                extra={"error": str(exc), "id": id},
            )
            raise
        record_id = record.get("id") if isinstance(record, dict) else None
        logger.info(
            "cupcake_fetch_succeeded",
            extra={"id": record_id},
        )
        return record

    register_metadata_routes(mcp)

    return mcp


if __name__ == "__main__":
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
