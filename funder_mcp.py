from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List

from fastmcp.server import FastMCP

from research_base import ResearchBase, ResearchConfig


class FunderConfig(ResearchConfig):
    """Configuration container for funder specific research."""

    # NOTE: we'll keep the incoming variable soup in one big mapping so future
    # agents can add/remove keys without modifying the class signature. 🚧
    funder_vars: Dict[str, Any] = {}


class FunderResearchBase(ResearchBase):
    """Research base with traversal packet evaluation for funder data."""

    def __init__(self, config: FunderConfig | None = None):
        # 🧠 Step 1: hydrate the parent loader
        super().__init__(config or FunderConfig())

        # 🚧 Each variable found in the config gets a placeholder slot for later
        self.vars: Dict[str, Any] = {k: None for k in self.config.funder_vars}

    # -- traversal packet generator
    def traverse_packets(self) -> Iterable[dict]:
        """Break records into lightweight packets for downstream loops."""
        for rec in self.records:
            # Delegated implementers can enrich the packet schema here later.
            yield {
                "record": rec,
                "quality": self._quality_score(rec),
            }

    # -- evaluation loop with fallback handling
    def evaluate(self) -> Dict[str, Any]:
        """Sequential pass for simple use cases."""
        for packet in self.traverse_packets():
            self._update_from_packet(packet)
        # apply final fallbacks from config
        for k, v in self.config.funder_vars.items():
            self.vars.setdefault(k, v)
        return self.vars

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


class Coordinator:
    """Simple orchestrator running evaluation in parallel and sequential modes."""

    def __init__(self, base: FunderResearchBase) -> None:
        self.base = base

    async def run(self) -> Dict[str, Any]:
        """Kick off the packet collection and merge results."""
        # parallel collection of packets – this keeps things snappy even if
        # record enumeration grows later.
        packets = await asyncio.gather(*[self._async_packet(p) for p in self.base.traverse_packets()])

        # sequential evaluation to keep ordering deterministic
        for p in packets:
            self.base._update_from_packet(p)
        for k, v in self.base.config.funder_vars.items():
            self.base.vars.setdefault(k, v)
        return self.base.vars

    async def _async_packet(self, packet: dict) -> dict:
        """Trivial async wrapper – placeholder for future I/O bound work."""
        return packet


def create_server(config: FunderConfig | None = None) -> FastMCP:
    # 🚧 bootstrap our research base and coordinator
    base = FunderResearchBase(config)
    coord = Coordinator(base)
    # 🧩 the MCP server wires in only one tool for now
    mcp = FastMCP(name=base.config.name, instructions=base.config.instructions)

    @mcp.tool()
    async def evaluate(query: str | None = None) -> Dict[str, Any]:
        """Run the coordinated evaluation and return variables."""
        # query is ignored today but kept for API parity – future agents could
        # use it as a hint for filtering.
        _ = query
        return await coord.run()

    return mcp


if __name__ == "__main__":
    # Running stand-alone for local testing
    create_server().run(transport="sse", host="127.0.0.1", port=8000)
