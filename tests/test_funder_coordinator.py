from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from funder_mcp import Coordinator, FunderConfig, FunderResearchBase


@pytest.fixture()
def funder_records(tmp_path: Path) -> Path:
    records = []
    for idx in range(8):
        records.append(
            {
                "id": f"rec-{idx}",
                "title": f"Record {idx}",
                "text": "",
                "metadata": {"lead": f"lead-{idx}"},
            }
        )
    target = tmp_path / "records.json"
    target.write_text(json.dumps(records))
    return target


class TrackingCoordinator(Coordinator):
    def __init__(self, base: FunderResearchBase, *, max_concurrency: int) -> None:
        super().__init__(base, max_concurrency=max_concurrency)
        self.max_observed = 0
        self._active = 0

    async def _async_packet(self, packet: dict) -> dict:
        self._active += 1
        self.max_observed = max(self.max_observed, self._active)
        try:
            await asyncio.sleep(0)
            return await super()._async_packet(packet)
        finally:
            self._active -= 1


@pytest.mark.asyncio()
async def test_coordinator_throttles_concurrency(funder_records: Path) -> None:
    config = FunderConfig(
        records_path=str(funder_records),
        funder_vars={"lead": None},
        max_packet_concurrency=3,
    )
    base = FunderResearchBase(config)
    coord = TrackingCoordinator(base, max_concurrency=3)
    result = await coord.run()
    assert result["lead"] == "lead-0"
    assert coord.max_observed <= 3


@pytest.mark.asyncio()
async def test_query_filters_records(funder_records: Path) -> None:
    config = FunderConfig(
        records_path=str(funder_records),
        funder_vars={"lead": None},
        max_packet_concurrency=2,
    )
    base = FunderResearchBase(config)
    coord = Coordinator(base, max_concurrency=2)
    result = await coord.run(query="Record 5")
    assert result["lead"] == "lead-5"
