from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import structlog
from fastmcp.server import FastMCP
from pydantic import Field

from logging_config import configure_logging
from research_base import ResearchBase, ResearchConfig
from validators import ValidationError, sanitize_query


configure_logging()
LOGGER = structlog.get_logger("funder_mcp")


class FunderConfig(ResearchConfig):
    """Configuration container for funder specific research."""

    funder_vars: Dict[str, Any] = {}
    max_concurrency: int = Field(default=10, ge=1)

    def __init__(self, **data: Any) -> None:
        env_value = os.getenv("FUNDER_MAX_CONCURRENCY")
        if env_value is not None and "max_concurrency" not in data:
            try:
                data["max_concurrency"] = int(env_value)
            except ValueError:
                LOGGER.warning("invalid_max_concurrency_env", value=env_value)
        super().__init__(**data)


class FunderResearchBase(ResearchBase):
    """Research base with traversal packet evaluation for funder data."""

    def __init__(self, config: FunderConfig | None = None):
        super().__init__(config or FunderConfig())
        self.reset_vars()

    def reset_vars(self) -> None:
        self.vars: Dict[str, Any] = {k: None for k in self.config.funder_vars}

    def traverse_packets(self, query: str | None = None) -> Iterable[dict]:
        """Break records into lightweight packets for downstream loops."""
        records: Sequence[dict]
        if query:
            records = self.search(query)
            self.logger.info(
                "traverse_packets_filtered",
                query=query,
                count=len(records),
            )
        else:
            records = self.records
            self.logger.info("traverse_packets_all", count=len(records))

        for rec in records:
            yield {
                "record": rec,
                "quality": self._quality_score(rec),
            }

    def evaluate(self, query: str | None = None) -> Dict[str, Any]:
        """Sequential evaluation primarily used for synchronous flows."""
        self.reset_vars()
        normalized_query = sanitize_query(query) if query else None
        for packet in self.traverse_packets(query=normalized_query):
            self._update_from_packet(packet)
        for key, value in self.config.funder_vars.items():
            self.vars.setdefault(key, value)
        self.logger.info("evaluation_completed", vars_resolved=len(self.vars))
        return dict(self.vars)

    def _update_from_packet(self, packet: dict) -> None:
        data = packet["record"].get("metadata", {})
        for key in self.vars:
            if key in data and self.vars[key] is None:
                self.vars[key] = data[key]

    def _quality_score(self, record: dict) -> float:
        fields = [record.get("title"), record.get("text"), record.get("metadata")]
        score = sum(1 for f in fields if f) / len(fields)
        return score


class Coordinator:
    """Orchestrates evaluation with bounded concurrency."""

    def __init__(self, base: FunderResearchBase, max_concurrency: Optional[int] = None) -> None:
        self.base = base
        self.max_concurrency = max_concurrency or self.base.config.max_concurrency
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def run(self, query: str | None = None) -> Dict[str, Any]:
        normalized_query = sanitize_query(query) if query else None
        self.logger.info(
            "coordinator_run_started",
            query=normalized_query,
            max_concurrency=self.max_concurrency,
        )
        self.base.reset_vars()
        packets = await self._collect_packets(normalized_query)
        for packet in packets:
            self.base._update_from_packet(packet)
        for key, value in self.base.config.funder_vars.items():
            self.base.vars.setdefault(key, value)
        resolved = {k: v for k, v in self.base.vars.items() if v is not None}
        self.logger.info(
            "coordinator_run_completed",
            packets=len(packets),
            resolved=len(resolved),
        )
        return dict(self.base.vars)

    async def _collect_packets(self, query: str | None) -> List[dict]:
        tasks: set[asyncio.Task[Tuple[int, dict]]] = set()
        packets: List[Tuple[int, dict]] = []
        for index, packet in enumerate(self.base.traverse_packets(query=query)):
            tasks.add(asyncio.create_task(self._run_packet(packet, index)))
            if len(tasks) >= self.max_concurrency:
                packets.extend(await self._wait_for_tasks(tasks, drain=False))

        packets.extend(await self._wait_for_tasks(tasks, drain=True))
        packets.sort(key=lambda item: item[0])
        ordered_packets = [packet for _, packet in packets]
        self.logger.debug("packets_collected", total=len(ordered_packets))
        return ordered_packets

    async def _run_packet(self, packet: dict, index: int) -> Tuple[int, dict]:
        result = await self._async_packet(packet)
        return index, result

    async def _wait_for_tasks(
        self, tasks: set[asyncio.Task[Tuple[int, dict]]], *, drain: bool
    ) -> List[Tuple[int, dict]]:
        if not tasks:
            return []
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.ALL_COMPLETED if drain else asyncio.FIRST_COMPLETED,
        )
        tasks.clear()
        tasks.update(pending)
        return [task.result() for task in done]

    async def _async_packet(self, packet: dict) -> dict:
        return packet


def create_server(config: FunderConfig | None = None) -> FastMCP:
    base = FunderResearchBase(config)
    coord = Coordinator(base)
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def evaluate(query: str | None = None) -> Dict[str, Any]:
        LOGGER.info("evaluate_tool_invoked", query=query)
        try:
            result = await coord.run(query=query)
        except ValidationError:
            LOGGER.warning("evaluate_tool_validation_failed", query=query)
            raise
        LOGGER.info("evaluate_tool_completed", query=query, resolved=len(result))
        return result

    return mcp


if __name__ == "__main__":
    # Running stand-alone for local testing
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
