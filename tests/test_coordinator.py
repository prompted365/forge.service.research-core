import asyncio

import pytest

from funder_mcp import Coordinator, FunderConfig, FunderResearchBase


@pytest.mark.asyncio
async def test_coordinator_filters_records_by_query():
    records = [
        {"id": "alpha-1", "title": "Alpha", "metadata": {"owner": "alice"}},
        {"id": "beta-2", "title": "Beta", "metadata": {"owner": "bob"}},
    ]
    config = FunderConfig(records_data=records, funder_vars={"owner": "unknown"})
    base = FunderResearchBase(config)
    result = await Coordinator(base, max_concurrency=2).run(query="Alpha")
    assert result["owner"] == "alice"


class TrackingCoordinator(Coordinator):
    def __init__(self, base: FunderResearchBase, max_concurrency: int) -> None:
        super().__init__(base, max_concurrency=max_concurrency)
        self._active = 0
        self.max_observed = 0

    async def _async_packet(self, packet: dict) -> dict:
        self._active += 1
        self.max_observed = max(self.max_observed, self._active)
        await asyncio.sleep(0.01)
        try:
            return await super()._async_packet(packet)
        finally:
            self._active -= 1


@pytest.mark.asyncio
async def test_coordinator_throttles_concurrency():
    records = [
        {"id": f"rec-{idx}", "title": f"Record {idx}", "metadata": {"owner": f"owner-{idx}"}}
        for idx in range(10)
    ]
    config = FunderConfig(records_data=records, funder_vars={"owner": None})
    base = FunderResearchBase(config)
    tracker = TrackingCoordinator(base, max_concurrency=3)
    await tracker.run()
    assert tracker.max_observed <= 3
