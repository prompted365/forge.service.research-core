from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Any

from pydantic_settings import BaseSettings

from logging_utils import get_logger

logger = get_logger(__name__)


class ResearchConfig(BaseSettings):
    """Configuration for research servers."""

    name: str = "Research MCP"
    instructions: str = "Search records"
    records_path: str = "records.json"
    default_search: str = "simple"
    extra_vars: Dict[str, Any] = {}
    fail_on_missing_records: bool = True
    max_query_length: int = 512
    max_identifier_length: int = 128


class ResearchBase:
    """Simple research base with pluggable search strategies."""

    def __init__(self, config: ResearchConfig | None = None):
        self.config = config or ResearchConfig()
        self.records = self._load_records(self.config.records_path)
        self.lookup = self._build_lookup(self.records)
        self.search_methods: Dict[str, Callable[[Iterable[dict], str], List[dict]]] = {}
        # register built-in strategy
        self.register_search("simple", self._simple_search)

    def _load_records(self, path: str) -> List[dict]:
        p = Path(path)
        if not p.exists():
            message = "Records file not found"
            if self.config.fail_on_missing_records:
                logger.error(
                    "records_missing",
                    extra={"path": str(p), "detail": message},
                )
                raise FileNotFoundError(f"Records file not found: {path}")
            logger.warning(
                "records_missing",
                extra={
                    "path": str(p),
                    "detail": message,
                    "action": "using_empty_dataset",
                },
            )
            return []
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            logger.error(
                "records_invalid_json",
                extra={"path": str(p), "error": str(exc)},
            )
            raise
        if not isinstance(data, list):
            logger.error("records_invalid_structure", extra={"path": str(p)})
            raise ValueError("Records file must contain a list of records")
        logger.info(
            "records_loaded",
            extra={"path": str(p), "count": len(data)},
        )
        return data

    def _build_lookup(self, records: Iterable[dict]) -> Dict[str, dict]:
        lookup: Dict[str, dict] = {}
        for record in records:
            identifier = record.get("id")
            if not isinstance(identifier, str):
                logger.warning(
                    "record_missing_identifier",
                    extra={"record": record},
                )
                continue
            clean_identifier = identifier.strip()
            if not clean_identifier:
                logger.warning(
                    "record_empty_identifier",
                    extra={"record": record},
                )
                continue
            lookup[clean_identifier] = record
        return lookup

    def register_search(
        self, name: str, func: Callable[[Iterable[dict], str], List[dict]]
    ) -> None:
        logger.info("search_strategy_registered", extra={"strategy_name": name})
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

    def _normalize_query(self, query: str) -> str:
        if not isinstance(query, str):
            logger.warning(
                "invalid_query_type", extra={"query_type": type(query).__name__}
            )
            raise ValueError("query must be a string")
        normalized = query.strip()
        if not normalized:
            logger.warning("invalid_query_empty")
            raise ValueError("query cannot be empty")
        if len(normalized) > self.config.max_query_length:
            logger.warning(
                "invalid_query_length",
                extra={
                    "length": len(normalized),
                    "max_length": self.config.max_query_length,
                },
            )
            raise ValueError("query is too long")
        if any(ord(ch) < 32 for ch in normalized):
            logger.warning("invalid_query_control_characters")
            raise ValueError("query contains control characters")
        return normalized

    def _normalize_identifier(self, identifier: str) -> str:
        if not isinstance(identifier, str):
            logger.warning(
                "invalid_identifier_type",
                extra={"identifier_type": type(identifier).__name__},
            )
            raise ValueError("id must be a string")
        clean_identifier = identifier.strip()
        if not clean_identifier:
            logger.warning("invalid_identifier_empty")
            raise ValueError("id cannot be empty")
        if len(clean_identifier) > self.config.max_identifier_length:
            logger.warning(
                "invalid_identifier_length",
                extra={
                    "length": len(clean_identifier),
                    "max_length": self.config.max_identifier_length,
                },
            )
            raise ValueError("id is too long")
        if any(ord(ch) < 32 for ch in clean_identifier):
            logger.warning("invalid_identifier_control_characters")
            raise ValueError("id contains control characters")
        return clean_identifier

    def search(self, query: str, *, method: str | None = None) -> List[dict]:
        normalized_query = self._normalize_query(query)
        resolved_method_raw = method if method is not None else self.config.default_search
        if not isinstance(resolved_method_raw, str):
            logger.warning(
                "invalid_search_method_type",
                extra={"method_type": type(resolved_method_raw).__name__},
            )
            raise ValueError("search method must be a string")
        resolved_method = resolved_method_raw.strip()
        if not resolved_method:
            logger.warning("invalid_search_method_empty")
            raise ValueError("search method cannot be empty")
        if resolved_method not in self.search_methods:
            logger.warning(
                "unknown_search_method",
                extra={"method": resolved_method},
            )
            raise ValueError(f"unknown search method: {resolved_method}")
        logger.info(
            "search_request",
            extra={
                "method": resolved_method,
                "query_preview": normalized_query[:80],
            },
        )
        results = self.search_methods[resolved_method](self.records, normalized_query)
        logger.info(
            "search_complete",
            extra={
                "method": resolved_method,
                "query_preview": normalized_query[:80],
                "result_count": len(results),
            },
        )
        return results

    def fetch(self, id: str) -> dict:
        normalized_identifier = self._normalize_identifier(id)
        if normalized_identifier not in self.lookup:
            logger.warning(
                "fetch_missing",
                extra={"id": normalized_identifier},
            )
            raise ValueError("unknown id")
        logger.info("fetch_hit", extra={"id": normalized_identifier})
        return self.lookup[normalized_identifier]
