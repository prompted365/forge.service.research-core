# Research MCP Service Toolkit

This repository bundles production-ready examples of Model Context Protocol (MCP) research servers. Each service layers
structured logging, strong input validation, configurable data sources, and concurrency-aware packet processing on top
of the baseline FastMCP primitives.

## Highlights

- **Structured JSON logging**: every tool call and data access emits machine-friendly log lines for observability stacks.
- **Hygienic inputs**: query strings, identifiers, and search methods are validated and normalised before execution.
- **Configurable records**: load datasets from any path (including environment overrides) with graceful empty fallbacks.
- **Funder evaluation throttle**: packet batching keeps async workloads bounded even with large corpora.
- **Modern packaging**: dependencies live in `pyproject.toml` with reproducible lock files and optional development extras.
- **Automated testing & CI**: pytest-based unit tests cover core behaviour and run via GitHub Actions.

## Installation

```shell
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock  # or requirements.lock for runtime-only installs
```

Alternatively, install the project editable with optional tooling:

```shell
pip install -e .[dev]
```

## Running the servers

All servers expose SSE transport on `http://127.0.0.1:8000` by default.

### Cupcake research demo

```shell
python sample_mcp.py
```

- Override the dataset location with `CUPCAKE_RECORDS_PATH=/path/to/records.json`.
- Missing files are handled gracefully; searches simply return no hits.

### Generic research server

```shell
python general_mcp.py
```

Use this flavour when you want to re-use the `ResearchBase` search and fetch primitives directly.

### Funder traversal + evaluation

```shell
python funder_mcp.py
```

The funder server streams records into packets, throttles async collection, and merges results back into a
configurable variable map. Pass an optional `query` argument when calling the `evaluate` tool to limit processing to
matching records.

## Testing

```shell
pytest
```

## Repository structure

- `research_base.py` – shared configuration, validation, and search helpers.
- `general_mcp.py` – generic MCP interface for search/fetch workflows.
- `sample_mcp.py` – cupcake-themed example with configurable records source.
- `funder_mcp.py` – traversal/evaluation pipeline for funder-style metadata extraction.
- `logging_utils.py` – JSON logger setup consumed by every server.
- `tests/` – pytest suite covering validation, concurrency throttling, and configuration helpers.
- `requirements.lock` / `requirements-dev.lock` – reproducible dependency locks generated via `pip-compile`.
- `.github/workflows/ci.yml` – GitHub Actions workflow for lint-free installs and automated tests.
