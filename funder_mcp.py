from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List

from fastmcp.server import FastMCP

from logging_utils import get_logger
from research_base import ResearchBase, ResearchConfig

logger = get_logger(__name__)


class FunderConfig(ResearchConfig):
    """Configuration container for funder specific research."""

    # NOTE: we'll keep the incoming variable soup in one big mapping so future
    # agents can add/remove keys without modifying the class signature. 🚧
    funder_vars: Dict[str, Any] = {}
    max_packet_concurrency: int = 10


class FunderResearchBase(ResearchBase):
    """Research base with traversal packet evaluation for funder data."""

    def __init__(self, config: FunderConfig | None = None):
        super().__init__(config or FunderConfig())
        self.reset_vars()

    def reset_vars(self) -> None:
        self.vars: Dict[str, Any] = {k: None for k in self.config.funder_vars}

    # -- traversal packet generator
    def traverse_packets(self, query: str | None = None) -> Iterable[dict]:
        """Break records into lightweight packets for downstream loops."""
        if query is None:
            records = self.records
        else:
            normalized = self._normalize_query(query)
            candidate_records = self.search(normalized)
            normalized_lower = normalized.lower()
            filtered = [
                rec
                for rec in candidate_records
                if normalized_lower in self._record_summary(rec)
            ]
            records = filtered or candidate_records
        for rec in records:
            yield {
                "record": rec,
                "quality": self._quality_score(rec),
            }

    # -- evaluation loop with fallback handling
    def evaluate(self, query: str | None = None) -> Dict[str, Any]:
        """Sequential pass for simple use cases."""
        self.reset_vars()
        for packet in self.traverse_packets(query=query):
            self._update_from_packet(packet)
        self._apply_fallbacks()
        return dict(self.vars)

    def _apply_fallbacks(self) -> None:
        for k, v in self.config.funder_vars.items():
            self.vars.setdefault(k, v)

    def _update_from_packet(self, packet: dict) -> None:
        """Merge packet info into our variable store with gentle overwrite."""
        data = packet["record"].get("metadata", {})
        for key in self.vars:
            if key in data and self.vars[key] is None:
                self.vars[key] = data[key]

    def _quality_score(self, record: dict) -> float:
        """Very naive quality heuristic – can be swapped out later."""
        fields = [record.get("title"), record.get("text"), record.get("metadata")]
        score = sum(1 for f in fields if f) / len(fields)
        return score

    def _record_summary(self, record: dict) -> str:
        parts = [
            record.get("title", ""),
            record.get("text", ""),
            " ".join(str(v) for v in record.get("metadata", {}).values()),
        ]
        return " ".join(parts).lower()


class Coordinator:
    """Simple orchestrator running evaluation in parallel and sequential modes."""

    def __init__(self, base: FunderResearchBase, *, max_concurrency: int | None = None) -> None:
        self.base = base
        self._max_concurrency = max(1, max_concurrency or self.base.config.max_packet_concurrency)

    async def run(self, query: str | None = None) -> Dict[str, Any]:
        """Kick off the packet collection and merge results."""
        self.base.reset_vars()
        query_preview = query.strip()[:80] if isinstance(query, str) else None
        logger.info(
            "funder_evaluation_started",
            extra={
                "query_preview": query_preview,
                "max_concurrency": self._max_concurrency,
            },
        )
        packets_iter = self.base.traverse_packets(query=query)
        batch: List[dict] = []
        for packet in packets_iter:
            batch.append(packet)
            if len(batch) >= self._max_concurrency:
                await self._process_batch(batch)
                batch = []
        if batch:
            await self._process_batch(batch)
        self.base._apply_fallbacks()
        result = dict(self.base.vars)
        logger.info(
            "funder_evaluation_completed",
            extra={"assigned_vars": len(result)},
        )
        return result

    async def _process_batch(self, batch: List[dict]) -> None:
        results = await asyncio.gather(*(self._async_packet(packet) for packet in batch))
        for packet in results:
            self.base._update_from_packet(packet)

    async def _async_packet(self, packet: dict) -> dict:
        """Trivial async wrapper – placeholder for future I/O bound work."""
        return packet


def create_server(config: FunderConfig | None = None) -> FastMCP:
    base = FunderResearchBase(config)
    coord = Coordinator(base, max_concurrency=base.config.max_packet_concurrency)
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def evaluate(query: str | None = None) -> Dict[str, Any]:
        """Run the coordinated evaluation and return variables."""
        try:
            result = await coord.run(query=query)
        except ValueError as exc:
            logger.warning(
                "funder_evaluate_failed",
                extra={"error": str(exc), "query": query},
            )
            raise
        query_preview = query.strip()[:80] if isinstance(query, str) else None
        logger.info(
            "funder_evaluate_succeeded",
            extra={
                "query_preview": query_preview,
                "assigned_vars": len(result),
            },
        )
        return result

    return mcp


if __name__ == "__main__":
    # Running stand-alone for local testing
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
