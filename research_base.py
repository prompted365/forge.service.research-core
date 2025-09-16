from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

from logging_config import configure_logging
from validators import ValidationError, normalize_method_name, sanitize_query, validate_identifier


class ResearchConfig(BaseSettings):
    """Configuration for research servers."""

    model_config = SettingsConfigDict(env_prefix="RESEARCH_")

    name: str = "Research MCP"
    instructions: str = "Search records"
    records_path: str | None = "records.json"
    records_data: Sequence[dict] | None = None
    default_search: str = "simple"
    extra_vars: Dict[str, Any] = {}


class ResearchBase:
    """Simple research base with pluggable search strategies."""

    def __init__(self, config: ResearchConfig | None = None):
        configure_logging()
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.config = config or ResearchConfig()
        default_method = normalize_method_name(self.config.default_search) or "simple"
        self.config.default_search = default_method
        self.records = self._load_records()
        self.lookup = {r["id"]: r for r in self.records}
        self.search_methods: Dict[str, Callable[[Iterable[dict], str], List[dict]]] = {}
        self.register_search("simple", self._simple_search)

    def _load_records(self) -> List[dict]:
        if self.config.records_data is not None:
            records = list(self.config.records_data)
            self.logger.info("records_loaded_from_memory", count=len(records))
            return records

        if not self.config.records_path:
            self.logger.warning("records_missing_source")
            return []

        path = Path(self.config.records_path)
        if not path.exists():
            self.logger.warning("records_file_missing", path=str(path))
            return []

        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            self.logger.error("records_parse_error", path=str(path), error=str(exc))
            return []

        if not isinstance(data, list):
            self.logger.error("records_invalid_format", path=str(path))
            return []

        self.logger.info("records_loaded_from_file", path=str(path), count=len(data))
        return data

    def register_search(
        self, name: str, func: Callable[[Iterable[dict], str], List[dict]]
    ) -> None:
        method = normalize_method_name(name)
        if not method:
            raise ValidationError("search method name cannot be empty")
        self.search_methods[method] = func
        self.logger.debug("search_method_registered", method=method)

    def _simple_search(self, records: Iterable[dict], query: str) -> List[dict]:
        toks = query.lower().split()
        hits: List[dict] = []
        for record in records:
            hay = " ".join(
                [
                    record.get("title", ""),
                    record.get("text", ""),
                    " ".join(record.get("metadata", {}).values()),
                ]
            ).lower()
            if any(token in hay for token in toks):
                hits.append(record)
        return hits

    def search(self, query: str, *, method: str | None = None) -> List[dict]:
        sanitized_query = sanitize_query(query)
        method_name = normalize_method_name(method) or self.config.default_search
        if method_name not in self.search_methods:
            self.logger.warning("unknown_search_method", method=method_name)
            raise ValidationError(f"unknown search method: {method_name}")
        results = self.search_methods[method_name](self.records, sanitized_query)
        self.logger.info(
            "search_completed",
            method=method_name,
            query=sanitized_query,
            hits=len(results),
        )
        return results

    def fetch(self, record_id: str) -> dict:
        identifier = validate_identifier(record_id)
        if identifier not in self.lookup:
            self.logger.warning("record_not_found", id=identifier)
            raise ValidationError("unknown id")
        self.logger.info("record_fetched", id=identifier)
        return self.lookup[identifier]
