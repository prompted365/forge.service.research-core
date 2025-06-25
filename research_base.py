from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Any

from pydantic_settings import BaseSettings


class ResearchConfig(BaseSettings):
    """Configuration for research servers."""

    name: str = "Research MCP"
    instructions: str = "Search records"
    records_path: str = "records.json"
    default_search: str = "simple"
    extra_vars: Dict[str, Any] = {}


class ResearchBase:
    """Simple research base with pluggable search strategies."""

    def __init__(self, config: ResearchConfig | None = None):
        self.config = config or ResearchConfig()
        self.records = self._load_records(self.config.records_path)
        self.lookup = {r["id"]: r for r in self.records}
        self.search_methods: Dict[str, Callable[[Iterable[dict], str], List[dict]]] = {}
        # register built-in strategy
        self.register_search("simple", self._simple_search)

    @staticmethod
    def _load_records(path: str) -> List[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Records file not found: {path}")
        return json.loads(p.read_text())

    def register_search(
        self, name: str, func: Callable[[Iterable[dict], str], List[dict]]
    ) -> None:
        self.search_methods[name] = func

    # default search implementation
    def _simple_search(self, records: Iterable[dict], query: str) -> List[dict]:
        toks = query.lower().split()
        hits: List[dict] = []
        for r in records:
            hay = " ".join(
                [r.get("title", ""), r.get("text", ""), " ".join(r.get("metadata", {}).values())]
            ).lower()
            if any(t in hay for t in toks):
                hits.append(r)
        return hits

    def search(self, query: str, *, method: str | None = None) -> List[dict]:
        method = method or self.config.default_search
        if method not in self.search_methods:
            raise ValueError(f"unknown search method: {method}")
        return self.search_methods[method](self.records, query)

    def fetch(self, id: str) -> dict:
        if id not in self.lookup:
            raise ValueError("unknown id")
        return self.lookup[id]
