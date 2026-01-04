"""MCP Server with tools for Jaeger trace analysis."""

# =============================================================================
# BOOTSTRAP LOGGING - This runs IMMEDIATELY on import to catch early crashes
# =============================================================================
import logging
import os
import sys

# Set up emergency logging before any other imports can fail
_bootstrap_log_file = os.environ.get("OTEL_MCP_DEBUG_LOG_FILE")
if _bootstrap_log_file:
    try:
        _log_path = os.path.join(os.getcwd(), _bootstrap_log_file)
        _bootstrap_handler = logging.FileHandler(_log_path, mode="w")
        _bootstrap_handler.setLevel(logging.DEBUG)
        _bootstrap_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(_bootstrap_handler)
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().debug(f"Bootstrap logging initialized: {_log_path}")
        logging.getLogger().debug(f"Python version: {sys.version}")
        logging.getLogger().debug(f"Working directory: {os.getcwd()}")
    except Exception as e:
        # Write to stderr as last resort
        print(f"BOOTSTRAP LOG ERROR: {e}", file=sys.stderr)

# =============================================================================
# Normal imports - any crash here will now be logged
# noqa: E402 comments needed because bootstrap logging MUST run before imports
# =============================================================================
import json  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
from fastmcp import FastMCP  # noqa: E402

from otel_mcp.backends.base import BaseBackend  # noqa: E402
from otel_mcp.backends.jaeger import JaegerBackend  # noqa: E402
from otel_mcp.config import BackendType, Settings, get_settings  # noqa: E402
from otel_mcp.models import TraceQuery  # noqa: E402
from otel_mcp.telemetry import setup_telemetry, traced  # noqa: E402

# Load environment variables
load_dotenv()

# Logger instance
logger = logging.getLogger(__name__)

# Global backend instance
_backend: BaseBackend | None = None

# Initialize FastMCP server
mcp = FastMCP("otel-mcp")


def _create_backend() -> BaseBackend:
    """Create backend instance based on configuration."""
    settings = get_settings()

    if settings.backend_type == BackendType.JAEGER:
        logger.info(f"Initializing Jaeger backend: {settings.jaeger_url}")
        return JaegerBackend(
            url=settings.jaeger_url,
            timeout=settings.jaeger_timeout,
        )
    else:
        raise ValueError(f"Unsupported backend type: {settings.backend_type}")


async def _get_backend() -> BaseBackend:
    """Get or lazily create backend."""
    global _backend

    if _backend is None:
        logger.info("Creating backend in current event loop")
        _backend = _create_backend()

        try:
            health = await _backend.health_check()
            logger.info(f"Backend health check: {health.status}")
            if health.status != "healthy":
                logger.warning("Backend is not healthy, but continuing...")
        except Exception as e:
            logger.error(f"Backend health check failed: {e}")

    return _backend


def _json_response(data: dict[str, object] | list[object] | str) -> str:
    """Convert data to JSON string response."""
    if isinstance(data, str):
        return data
    return json.dumps(data, default=str, indent=2)


# =============================================================================
# Service Discovery Tools
# =============================================================================


@mcp.tool()
@traced("mcp.list_services")
async def list_services() -> str:
    """List all available services being traced in Jaeger.

    Call this FIRST to discover what services exist before searching traces.
    Services are applications/microservices sending telemetry to Jaeger.

    Returns:
        JSON with 'services' (list of service names) and 'count'.
        Example: {"services": ["user-service", "order-service"], "count": 2}
    """
    try:
        backend = await _get_backend()
        services = await backend.list_services()
        return _json_response({"services": services, "count": len(services)})
    except Exception as e:
        logger.error(f"Error listing services: {e}", exc_info=True)
        return _json_response({"error": str(e)})


@mcp.tool()
@traced("mcp.list_operations")
async def list_operations(service_name: str) -> str:
    """List all operations (endpoints/functions) for a specific service.

    Use this after list_services() to see what operations a service performs.
    Operations are typically HTTP endpoints, RPC methods, or function names.

    Args:
        service_name: Name of the service (from list_services)

    Returns:
        JSON with 'operations' list and 'count'.
        Example: {"service": "user-service", "operations": ["GET /users", "POST /users"], "count": 2}
    """
    try:
        backend = await _get_backend()
        operations = await backend.get_operations(service_name)
        return _json_response({
            "service": service_name,
            "operations": operations,
            "count": len(operations),
        })
    except Exception as e:
        logger.error(f"Error listing operations: {e}", exc_info=True)
        return _json_response({"error": str(e)})


# =============================================================================
# Trace Inspection Tools
# =============================================================================


@mcp.tool()
@traced("mcp.search_traces")
async def search_traces(
    service_name: str,
    operation_name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    has_error: bool | None = None,
    limit: int = 20,
) -> str:
    """Search for traces matching the given filters. Returns trace summaries with IDs.

    IMPORTANT: You MUST call list_services() first to get valid service names.
    This returns trace summaries - use get_trace(trace_id) to get full span details.

    Args:
        service_name: Service name (REQUIRED - get from list_services)
        operation_name: Filter by operation (get from list_operations)
        start_time: Start time in ISO 8601 format (e.g., "2024-01-01T00:00:00Z")
        end_time: End time in ISO 8601 format
        min_duration_ms: Only traces slower than this (in milliseconds)
        max_duration_ms: Only traces faster than this (in milliseconds)
        has_error: Set to true to find only failed traces
        limit: Max results (default: 20, max: 100)

    Returns:
        JSON with 'traces' list containing: trace_id, service, operation,
        start_time, duration_ms, span_count, has_error. Use trace_id with get_trace().
    """
    from datetime import datetime

    try:
        backend = await _get_backend()

        query = TraceQuery(
            service_name=service_name,
            operation_name=operation_name,
            start_time=datetime.fromisoformat(start_time) if start_time else None,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            has_error=has_error,
            limit=min(limit, 100),
        )

        traces = await backend.search_traces(query)

        # Convert to summaries
        summaries = [
            {
                "trace_id": t.trace_id,
                "service": t.service_name,
                "operation": t.root_operation,
                "start_time": t.start_time.isoformat(),
                "duration_ms": round(t.duration_ms, 2),
                "span_count": t.span_count,
                "has_error": t.has_error,
            }
            for t in traces
        ]

        return _json_response({"traces": summaries, "count": len(summaries)})
    except Exception as e:
        logger.error(f"Error searching traces: {e}", exc_info=True)
        return _json_response({"error": str(e)})


@mcp.tool()
@traced("mcp.get_trace")
async def get_trace(trace_id: str) -> str:
    """Get complete trace details including all spans and their relationships.

    Use this AFTER search_traces() to get full details of a specific trace.
    Shows the complete span tree with parent-child relationships, timing, and attributes.

    Args:
        trace_id: The trace_id from search_traces() results

    Returns:
        JSON with trace metadata and 'spans' array. Each span includes:
        span_id, parent_span_id, operation, service, duration_ms, status,
        has_error, error_message, and attributes (tags/metadata).
    """
    try:
        backend = await _get_backend()
        trace = await backend.get_trace(trace_id)

        # Format spans for readability
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
                "events": [
                    {"name": e.name, "timestamp": e.timestamp.isoformat(), "attributes": e.attributes}
                    for e in s.events
                ],
            }
            for s in trace.spans
        ]

        return _json_response({
            "trace_id": trace.trace_id,
            "service": trace.service_name,
            "root_operation": trace.root_operation,
            "start_time": trace.start_time.isoformat(),
            "duration_ms": round(trace.duration_ms, 2),
            "status": trace.status.value,
            "span_count": trace.span_count,
            "spans": spans,
        })
    except Exception as e:
        logger.error(f"Error getting trace: {e}", exc_info=True)
        return _json_response({"error": str(e)})


@mcp.tool()
@traced("mcp.find_errors")
async def find_errors(
    service_name: str,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 20,
) -> str:
    """Find traces that contain errors or failures.

    Use this to debug application errors. Returns traces where at least one
    span has an error status, along with error messages.

    Args:
        service_name: Service name (REQUIRED - get from list_services)
        start_time: Start time in ISO 8601 format (e.g., "2024-01-01T00:00:00Z")
        end_time: End time in ISO 8601 format
        limit: Max results (default: 20)

    Returns:
        JSON with 'error_traces' list. Each includes trace_id, error_count,
        and 'errors' array with span_id, operation, and error message.
    """
    from datetime import datetime

    try:
        backend = await _get_backend()

        query = TraceQuery(
            service_name=service_name,
            start_time=datetime.fromisoformat(start_time) if start_time else None,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
            has_error=True,
            limit=min(limit, 100),
        )

        traces = await backend.search_traces(query)

        # Extract error information
        error_traces = []
        for trace in traces:
            error_spans = [s for s in trace.spans if s.has_error]
            error_traces.append({
                "trace_id": trace.trace_id,
                "service": trace.service_name,
                "operation": trace.root_operation,
                "start_time": trace.start_time.isoformat(),
                "duration_ms": round(trace.duration_ms, 2),
                "error_count": len(error_spans),
                "errors": [
                    {
                        "span_id": s.span_id,
                        "operation": s.operation_name,
                        "message": s.error_message,
                    }
                    for s in error_spans[:5]  # Limit error details
                ],
            })

        return _json_response({"error_traces": error_traces, "count": len(error_traces)})
    except Exception as e:
        logger.error(f"Error finding errors: {e}", exc_info=True)
        return _json_response({"error": str(e)})


# =============================================================================
# Performance Analysis Tools
# =============================================================================


@mcp.tool()
@traced("mcp.get_slow_traces")
async def get_slow_traces(
    service_name: str,
    operation_name: str | None = None,
    min_duration_ms: int = 1000,
    limit: int = 10,
) -> str:
    """Find the slowest traces for performance analysis.

    Use this to identify performance bottlenecks. Returns traces sorted by
    duration (slowest first) that exceed the minimum duration threshold.

    Args:
        service_name: Service name (REQUIRED - get from list_services)
        operation_name: Filter to specific operation (get from list_operations)
        min_duration_ms: Only show traces slower than this (default: 1000ms = 1s)
        limit: Max results (default: 10)

    Returns:
        JSON with 'slow_traces' list sorted by duration_ms descending.
        Each includes trace_id, operation, duration_ms, span_count.
    """
    try:
        backend = await _get_backend()

        query = TraceQuery(
            service_name=service_name,
            operation_name=operation_name,
            min_duration_ms=min_duration_ms,
            limit=min(limit * 3, 100),  # Fetch more to sort
        )

        traces = await backend.search_traces(query)

        # Sort by duration descending
        sorted_traces = sorted(traces, key=lambda t: t.duration_ms, reverse=True)[:limit]

        slow_traces = [
            {
                "trace_id": t.trace_id,
                "service": t.service_name,
                "operation": t.root_operation,
                "start_time": t.start_time.isoformat(),
                "duration_ms": round(t.duration_ms, 2),
                "span_count": t.span_count,
            }
            for t in sorted_traces
        ]

        return _json_response({"slow_traces": slow_traces, "count": len(slow_traces)})
    except Exception as e:
        logger.error(f"Error finding slow traces: {e}", exc_info=True)
        return _json_response({"error": str(e)})


@mcp.tool()
@traced("mcp.get_operation_stats")
async def get_operation_stats(
    service_name: str,
    operation_name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> str:
    """Get aggregated performance statistics for a service or operation.

    Use this to understand overall service health and latency distribution.
    Calculates percentiles (p50, p95, p99) and error rates from recent traces.

    Args:
        service_name: Service name (REQUIRED - get from list_services)
        operation_name: Filter to specific operation (optional)
        start_time: Start time in ISO 8601 format
        end_time: End time in ISO 8601 format

    Returns:
        JSON with: sample_size, error_count, error_rate (percentage),
        and duration_ms object with min, max, avg, p50, p95, p99 latencies.
    """
    import statistics
    from datetime import datetime

    try:
        backend = await _get_backend()

        query = TraceQuery(
            service_name=service_name,
            operation_name=operation_name,
            start_time=datetime.fromisoformat(start_time) if start_time else None,
            end_time=datetime.fromisoformat(end_time) if end_time else None,
            limit=500,  # Sample size for stats
        )

        traces = await backend.search_traces(query)

        if not traces:
            return _json_response({"error": "No traces found for statistics"})

        durations = [t.duration_ms for t in traces]
        error_count = sum(1 for t in traces if t.has_error)

        # Calculate percentiles
        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        def percentile(data: list[float], p: float) -> float:
            k = (len(data) - 1) * (p / 100)
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f]) if c != f else data[f]

        stats = {
            "service": service_name,
            "operation": operation_name or "(all)",
            "sample_size": n,
            "request_count": n,
            "error_count": error_count,
            "error_rate": round(error_count / n * 100, 2) if n > 0 else 0,
            "duration_ms": {
                "min": round(min(durations), 2),
                "max": round(max(durations), 2),
                "avg": round(statistics.mean(durations), 2),
                "p50": round(percentile(sorted_durations, 50), 2),
                "p95": round(percentile(sorted_durations, 95), 2),
                "p99": round(percentile(sorted_durations, 99), 2),
            },
        }

        return _json_response(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        return _json_response({"error": str(e)})


def _setup_logging(settings: Settings) -> None:
    """Configure logging based on settings.

    CRITICAL: All logs go to STDERR or file, never STDOUT.
    STDOUT must contain ONLY JSON-RPC protocol messages for MCP.
    """
    import os

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Always log to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    # If debug log file is configured, also log to file
    if settings.debug_log_file:
        log_path = os.path.join(os.getcwd(), settings.debug_log_file)
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        # Force DEBUG level when file logging is enabled
        root_logger.setLevel(logging.DEBUG)
        root_logger.info(f"Debug logging enabled: {log_path}")


def main() -> None:
    """Run the MCP server."""
    settings = get_settings()

    # Configure logging (must be done before any log calls)
    _setup_logging(settings)

    # Set up self-telemetry
    setup_telemetry("otel-mcp")

    logger.info("Starting MCP Server")

    # Run the MCP server with banner suppressed
    # show_banner=False prevents FastMCP from printing to STDOUT
    # which would corrupt the JSON-RPC protocol stream used by stdio transport
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
