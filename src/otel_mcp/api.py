"""FastAPI REST API with OpenAPI documentation."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from otel_mcp.backends.base import BaseBackend
from otel_mcp.backends.jaeger import JaegerBackend
from otel_mcp.config import BackendType, get_settings
from otel_mcp.models import TraceQuery
from otel_mcp.telemetry import setup_telemetry

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global backend
_backend: BaseBackend | None = None


def _create_backend() -> BaseBackend:
    """Create backend instance based on configuration."""
    settings = get_settings()

    if settings.backend_type == BackendType.JAEGER:
        return JaegerBackend(
            url=settings.jaeger_url,
            timeout=settings.jaeger_timeout,
        )
    else:
        raise ValueError(f"Unsupported backend type: {settings.backend_type}")


async def get_backend() -> BaseBackend:
    """Get or create backend instance."""
    global _backend
    if _backend is None:
        _backend = _create_backend()
    return _backend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Setup
    settings = get_settings()
    setup_telemetry("otel-mcp-api")
    logger.info(f"Starting MCP API on {settings.api_host}:{settings.api_port}")

    yield

    # Cleanup
    global _backend
    if _backend:
        await _backend.close()
        _backend = None


# Create FastAPI app
app = FastAPI(
    title="Jaeger MCP Server API",
    description="REST API for Jaeger trace analysis during development",
    version="0.1.0",
    lifespan=lifespan,
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)


# =============================================================================
# Response Models
# =============================================================================


class HealthResponse(BaseModel):
    status: str
    backend: str
    url: str
    service_count: int | None = None
    error: str | None = None


class ServicesResponse(BaseModel):
    services: list[str]
    count: int


class OperationsResponse(BaseModel):
    service: str
    operations: list[str]
    count: int


class TraceSummaryResponse(BaseModel):
    trace_id: str
    service: str
    operation: str
    start_time: str
    duration_ms: float
    span_count: int
    has_error: bool


class TracesResponse(BaseModel):
    traces: list[TraceSummaryResponse]
    count: int


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check API and backend health."""
    backend = await get_backend()
    health = await backend.health_check()
    return HealthResponse(
        status=health.status,
        backend=health.backend,
        url=health.url,
        service_count=health.service_count,
        error=health.error,
    )


@app.get("/services", response_model=ServicesResponse, tags=["Discovery"])
async def list_services() -> ServicesResponse:
    """List all available services in Jaeger."""
    backend = await get_backend()
    services = await backend.list_services()
    return ServicesResponse(services=services, count=len(services))


@app.get("/services/{service_name}/operations", response_model=OperationsResponse, tags=["Discovery"])
async def list_operations(service_name: str) -> OperationsResponse:
    """List all operations for a service."""
    backend = await get_backend()
    operations = await backend.get_operations(service_name)
    return OperationsResponse(service=service_name, operations=operations, count=len(operations))


@app.get("/traces", response_model=TracesResponse, tags=["Traces"])
async def search_traces(
    service_name: str = Query(..., description="Service name (required)"),
    operation_name: str | None = Query(None, description="Operation name filter"),
    start_time: str | None = Query(None, description="Start time (ISO 8601)"),
    end_time: str | None = Query(None, description="End time (ISO 8601)"),
    min_duration_ms: int | None = Query(None, description="Minimum duration in ms"),
    max_duration_ms: int | None = Query(None, description="Maximum duration in ms"),
    has_error: bool | None = Query(None, description="Filter by error status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> TracesResponse:
    """Search for traces with filters."""
    backend = await get_backend()

    query = TraceQuery(
        service_name=service_name,
        operation_name=operation_name,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        has_error=has_error,
        limit=limit,
    )

    traces = await backend.search_traces(query)

    summaries = [
        TraceSummaryResponse(
            trace_id=t.trace_id,
            service=t.service_name,
            operation=t.root_operation,
            start_time=t.start_time.isoformat(),
            duration_ms=round(t.duration_ms, 2),
            span_count=t.span_count,
            has_error=t.has_error,
        )
        for t in traces
    ]

    return TracesResponse(traces=summaries, count=len(summaries))


@app.get("/traces/errors", response_model=TracesResponse, tags=["Traces"])
async def find_errors(
    service_name: str = Query(..., description="Service name (required)"),
    start_time: str | None = Query(None, description="Start time (ISO 8601)"),
    end_time: str | None = Query(None, description="End time (ISO 8601)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
) -> TracesResponse:
    """Find traces containing errors."""
    backend = await get_backend()

    query = TraceQuery(
        service_name=service_name,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
        has_error=True,
        limit=limit,
    )

    traces = await backend.search_traces(query)

    summaries = [
        TraceSummaryResponse(
            trace_id=t.trace_id,
            service=t.service_name,
            operation=t.root_operation,
            start_time=t.start_time.isoformat(),
            duration_ms=round(t.duration_ms, 2),
            span_count=t.span_count,
            has_error=True,
        )
        for t in traces
    ]

    return TracesResponse(traces=summaries, count=len(summaries))


@app.get("/traces/slow", response_model=TracesResponse, tags=["Performance"])
async def get_slow_traces(
    service_name: str = Query(..., description="Service name (required)"),
    operation_name: str | None = Query(None, description="Operation name filter"),
    min_duration_ms: int = Query(1000, description="Minimum duration threshold"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
) -> TracesResponse:
    """Find slowest traces."""
    backend = await get_backend()

    query = TraceQuery(
        service_name=service_name,
        operation_name=operation_name,
        min_duration_ms=min_duration_ms,
        limit=limit * 3,
    )

    traces = await backend.search_traces(query)

    # Sort by duration
    sorted_traces = sorted(traces, key=lambda t: t.duration_ms, reverse=True)[:limit]

    summaries = [
        TraceSummaryResponse(
            trace_id=t.trace_id,
            service=t.service_name,
            operation=t.root_operation,
            start_time=t.start_time.isoformat(),
            duration_ms=round(t.duration_ms, 2),
            span_count=t.span_count,
            has_error=t.has_error,
        )
        for t in sorted_traces
    ]

    return TracesResponse(traces=summaries, count=len(summaries))


@app.get("/traces/{trace_id}", tags=["Traces"])
async def get_trace(trace_id: str) -> JSONResponse:
    """Get complete trace details by ID."""
    backend = await get_backend()

    try:
        trace = await backend.get_trace(trace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    spans = [
        {
            "span_id": s.span_id,
            "parent_span_id": s.parent_span_id,
            "operation": s.operation_name,
            "service": s.service_name,
            "start_time": s.start_time.isoformat(),
            "duration_ms": round(s.duration_ms, 2),
            "status": s.status.value,
            "kind": s.kind.value,
            "has_error": s.has_error,
            "error_message": s.error_message,
            "attributes": s.attributes,
        }
        for s in trace.spans
    ]

    return JSONResponse({
        "trace_id": trace.trace_id,
        "service": trace.service_name,
        "root_operation": trace.root_operation,
        "start_time": trace.start_time.isoformat(),
        "duration_ms": round(trace.duration_ms, 2),
        "status": trace.status.value,
        "span_count": trace.span_count,
        "spans": spans,
    })


def main() -> None:
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    uvicorn.run(
        "otel_mcp.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
