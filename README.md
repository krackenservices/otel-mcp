# OTEL MCP Server

An MCP (Model Context Protocol) server for Jaeger trace analysis during development. Query and analyze distributed traces with AI assistance for debugging and performance optimization.

## Features

- **Service Discovery**: List services and operations in your Jaeger instance
- **Trace Inspection**: Search, filter, and inspect traces with full span details
- **Performance Analysis**: Find slow traces, get latency percentiles, error rates
- **REST API**: FastAPI endpoints with OpenAPI documentation at `/docs`
- **Self-Telemetry**: The server traces itself to Jaeger for debugging

## Installation

### Using uvx (Recommended)

Run directly without installing:

```bash
# Run MCP server
uvx otel-mcp

# Run REST API
uvx --from otel-mcp otel-mcp-api
```

### Using pip

```bash
pip install otel-mcp

# Then run
otel-mcp        # MCP server
otel-mcp-api    # REST API
```

### From Source

```bash
git clone https://github.com/ryanm101/otel-mcp.git
cd otel-mcp
uv sync
uv run otel-mcp
```

## Quick Start

### 1. Start Jaeger

```bash
docker-compose up -d
# Jaeger UI at http://localhost:16686
```

### 2. Run the MCP Server

```bash
uvx otel-mcp
# Or with environment variables:
JAEGER_URL=http://jaeger:16686 uvx otel-mcp
```

### 3. Or Run the REST API

```bash
uvx --from otel-mcp otel-mcp-api
# OpenAPI docs at http://localhost:8000/docs
```

## MCP Client Configuration

Add to your MCP client config (e.g., Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "otel-mcp": {
      "command": "uvx",
      "args": ["otel-mcp"],
      "env": {
        "JAEGER_URL": "http://localhost:16686"
      }
    }
  }
}
```

## Configuration

Create a `.env` file (see `.env.example`):

```env
JAEGER_URL=http://localhost:16686
JAEGER_TIMEOUT=30
LOG_LEVEL=INFO

# Debug logging (writes to file in working directory)
# DEBUG_LOG_FILE=otel-mcp.log

# Self-telemetry (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=otel-mcp
# OTEL_SDK_DISABLED=true  # Disable self-telemetry
```

## MCP Tools

### Service Discovery

| Tool | Description |
|------|-------------|
| `list_services` | List all services in Jaeger |
| `list_operations` | List operations for a service |

### Trace Inspection

| Tool | Description |
|------|-------------|
| `search_traces` | Search traces with filters (service, operation, duration, errors) |
| `get_trace` | Get complete trace by ID with all spans |
| `find_errors` | Find traces containing errors |

### Performance Analysis

| Tool | Description |
|------|-------------|
| `get_slow_traces` | Find slowest traces |
| `get_operation_stats` | Get latency percentiles (p50/p95/p99) and error rates |

## REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/services` | GET | List services |
| `/services/{name}/operations` | GET | List operations |
| `/traces` | GET | Search traces |
| `/traces/{trace_id}` | GET | Get trace by ID |
| `/traces/errors` | GET | Find error traces |
| `/traces/slow` | GET | Find slow traces |

## Development

### Run Tests

```bash
uv run pytest tests/ -v
```

### Run with Coverage

```bash
uv run pytest tests/ --cov=otel_mcp --cov-report=term-missing
```

### Lint and Type Check

```bash
uv run ruff check src/
uv run mypy src/
```

### Adding a New Backend

1. Create `backends/tempo.py` implementing `BaseBackend`
2. Add backend type to `config.py`
3. Update `_create_backend()` in `server.py` and `api.py`

## License

Apache-2.0
