# OTEL MCP Server

An MCP (Model Context Protocol) server for Jaeger trace analysis during development. Query and analyze distributed traces with AI assistance for debugging and performance optimization.

## Features

- **Service Discovery**: List services and operations in your Jaeger instance
- **Trace Inspection**: Search, filter, and inspect traces with full span details
- **Performance Analysis**: Find slow traces, get latency percentiles, error rates
- **REST API**: FastAPI endpoints with OpenAPI documentation at `/docs`
- **Self-Telemetry**: The server traces itself to Jaeger for debugging

## Quick Start

### 1. Start Jaeger

```bash
docker-compose up -d
# Jaeger UI at http://localhost:16686
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Run the MCP Server

```bash
uv run otel-mcp
```

### 4. Or Run the REST API

```bash
uv run otel-mcp-api
# OpenAPI docs at http://localhost:8000/docs
```

## Configuration

Create a `.env` file (see `.env.example`):

```env
JAEGER_URL=http://localhost:16686
JAEGER_TIMEOUT=30
LOG_LEVEL=INFO

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

## Architecture

```
src/otel_mcp/
├── server.py          # MCP server with tool definitions
├── api.py             # FastAPI REST endpoints
├── config.py          # Configuration management
├── models.py          # Pydantic data models
├── telemetry.py       # Self-instrumentation setup
└── backends/
    ├── base.py        # Abstract backend interface
    └── jaeger.py      # Jaeger implementation
```

### Adding a New Backend

1. Create `backends/tempo.py` implementing `BaseBackend`
2. Add backend type to `config.py`
3. Update `_create_backend()` in `server.py` and `api.py`

## License

Apache-2.0
