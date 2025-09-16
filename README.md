# Cupcake MCP for Deep Research

This project now provides a production-ready baseline for Deep Research style MCP servers with structured logging, configurable data sources, and automated tests.

## Set up & run

Python setup:

```shell
python -m venv env
source env/bin/activate
pip install -r requirements/dev.txt
pip install -e .
```

Run the cupcake demo server:

```shell
# optional: override the data file location
export CUPCAKE_RECORDS_PATH=/path/to/records.json
python sample_mcp.py
```

For a more generic research server, run:

```shell
# optional: override the shared research dataset
export RESEARCH_RECORDS_PATH=/path/to/records.json
python general_mcp.py
```

### Funder research example

```shell
# optional: bound the async workers
export FUNDER_MAX_CONCURRENCY=5
python funder_mcp.py
```

The server will start on `http://127.0.0.1:8000` using SSE transport.

## Files

- `sample_mcp.py`: Cupcake-specific example server
- `general_mcp.py`: Generic research server built on `research_base`
- `research_base.py`: Provides configuration and pluggable search strategies
- `records.json`: Example data file used by the demos (configurable via environment variables)
- `funder_mcp.py`: Example using traversal packets for funder configs with throttled concurrency
- `logging_config.py`: Shared structured logging bootstrapper
- `validators.py`: Sanitises inbound request parameters

## Development

- Runtime dependencies are pinned in `requirements/runtime.txt` (generated via `pip-compile`).
- Install development tooling with `pip install -r requirements/dev.txt`.
- Run the automated test suite with:

```shell
pytest
```

Structured JSON logs are emitted to standard output. They include event names (`message`), log level, timestamps, and contextual metadata to simplify production monitoring.
