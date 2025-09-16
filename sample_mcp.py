import json
import os
from pathlib import Path
from typing import Dict, List

import structlog
from fastmcp.server import FastMCP

from logging_config import configure_logging
from validators import ValidationError, sanitize_query, validate_identifier


configure_logging()
LOGGER = structlog.get_logger("sample_mcp")


def _resolve_records_path(records_path: str | None = None) -> Path | None:
    if records_path:
        return Path(records_path)
    env_path = os.getenv("CUPCAKE_RECORDS_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).with_name("records.json")


def _load_records(records_path: Path | None) -> List[dict]:
    if records_path is None:
        LOGGER.warning("records_path_not_provided")
        return []
    if not records_path.exists():
        LOGGER.warning("records_file_missing", path=str(records_path))
        return []
    try:
        payload = json.loads(records_path.read_text())
    except json.JSONDecodeError as exc:
        LOGGER.error("records_parse_error", path=str(records_path), error=str(exc))
        return []
    if not isinstance(payload, list):
        LOGGER.error("records_invalid_format", path=str(records_path))
        return []
    LOGGER.info("records_loaded", path=str(records_path), count=len(payload))
    return payload


def create_server(records_path: str | None = None) -> FastMCP:
    resolved_path = _resolve_records_path(records_path)
    records = _load_records(resolved_path)
    lookup: Dict[str, dict] = {record["id"]: record for record in records if "id" in record}
    mcp = FastMCP(name="Cupcake MCP", instructions="Search cupcake orders")

    @mcp.tool()
    async def search(query: str):
        """Search for cupcake orders – keyword match."""

        LOGGER.info("search_tool_invoked", query=query)
        sanitized_query = sanitize_query(query)
        tokens = sanitized_query.lower().split()
        ids: List[str] = []
        for record in records:
            record_id = record.get("id")
            if not record_id:
                continue
            haystack = " ".join(
                [
                    record.get("title", ""),
                    record.get("text", ""),
                    " ".join(record.get("metadata", {}).values()),
                ]
            ).lower()
            if any(token in haystack for token in tokens):
                ids.append(record_id)
        LOGGER.info("search_tool_completed", query=sanitized_query, hits=len(ids))
        return {"ids": ids}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch a cupcake order by ID."""

        LOGGER.info("fetch_tool_invoked", id=id)
        identifier = validate_identifier(id)
        try:
            record = lookup[identifier]
        except KeyError as exc:
            LOGGER.warning("record_not_found", id=identifier)
            raise ValidationError("unknown id") from exc
        LOGGER.info("fetch_tool_completed", id=identifier)
        return record

    return mcp


if __name__ == "__main__":
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
