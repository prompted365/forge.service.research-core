# Cupcake MCP for Deep Research

This is a minimal example of a Deep Research style MCP server for searching and fetching cupcake orders.

## Set up & run

Python setup:

```shell
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Run the cupcake demo server:

```shell
python sample_mcp.py
```

For a more generic research server, run:

```shell
python general_mcp.py
```

The server will start on `http://127.0.0.1:8000` using SSE transport.

## Files

- `sample_mcp.py`: Cupcake-specific example server
- `general_mcp.py`: Generic research server built on `research_base`
- `research_base.py`: Provides configuration and pluggable search strategies
- `records.json`: Example data file (must be present in the same directory)
