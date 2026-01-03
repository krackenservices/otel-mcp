"""Shared pytest fixtures for tests."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from otel_mcp.backends.jaeger import JaegerBackend
from otel_mcp.models import SpanData, SpanKind, SpanStatus, TraceData


@pytest.fixture
def sample_jaeger_trace() -> dict[str, Any]:
    """Sample Jaeger trace response data."""
    return {
        "traceID": "abc123def456",
        "spans": [
            {
                "traceID": "abc123def456",
                "spanID": "span1",
                "operationName": "HTTP GET /api/users",
                "processID": "p1",
                "startTime": 1704067200000000,  # 2024-01-01 00:00:00 UTC in microseconds
                "duration": 150000,  # 150ms in microseconds
                "references": [],
                "tags": [
                    {"key": "http.method", "value": "GET"},
                    {"key": "http.status_code", "value": 200},
                ],
                "logs": [],
            },
            {
                "traceID": "abc123def456",
                "spanID": "span2",
                "operationName": "db.query",
                "processID": "p1",
                "startTime": 1704067200050000,  # 50ms after root
                "duration": 80000,  # 80ms
                "references": [{"refType": "CHILD_OF", "spanID": "span1"}],
                "tags": [
                    {"key": "db.system", "value": "postgresql"},
                ],
                "logs": [],
            },
        ],
        "processes": {
            "p1": {"serviceName": "user-service"},
        },
    }


@pytest.fixture
def sample_jaeger_error_trace() -> dict[str, Any]:
    """Sample Jaeger trace with an error."""
    return {
        "traceID": "error123",
        "spans": [
            {
                "traceID": "error123",
                "spanID": "span1",
                "operationName": "HTTP GET /api/broken",
                "processID": "p1",
                "startTime": 1704067200000000,
                "duration": 50000,
                "references": [],
                "tags": [
                    {"key": "error", "value": True},
                    {"key": "otel.status_code", "value": "ERROR"},
                ],
                "logs": [
                    {
                        "timestamp": 1704067200010000,
                        "fields": [
                            {"key": "event", "value": "exception"},
                            {"key": "message", "value": "Connection refused"},
                        ],
                    }
                ],
            },
        ],
        "processes": {
            "p1": {"serviceName": "broken-service"},
        },
    }


@pytest.fixture
def sample_services() -> list[str]:
    """Sample service list."""
    return ["user-service", "order-service", "payment-service"]


@pytest.fixture
def sample_operations() -> list[str]:
    """Sample operations list."""
    return ["HTTP GET /api/users", "HTTP POST /api/users", "db.query"]


@pytest.fixture
def sample_trace_data() -> TraceData:
    """Sample parsed TraceData."""
    spans = [
        SpanData(
            trace_id="abc123",
            span_id="span1",
            parent_span_id=None,
            operation_name="HTTP GET /api/users",
            service_name="user-service",
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            duration_ms=150.0,
            status=SpanStatus.OK,
            kind=SpanKind.SERVER,
            attributes={"http.method": "GET"},
            events=[],
            has_error=False,
        ),
    ]

    return TraceData(
        trace_id="abc123",
        spans=spans,
        start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        duration_ms=150.0,
        service_name="user-service",
        root_operation="HTTP GET /api/users",
        status=SpanStatus.OK,
    )


@pytest.fixture
def mock_backend(sample_services: list[str], sample_trace_data: TraceData) -> AsyncMock:
    """Mock JaegerBackend for testing."""
    mock = AsyncMock(spec=JaegerBackend)
    mock.list_services.return_value = sample_services
    mock.get_operations.return_value = ["HTTP GET /api/users", "db.query"]
    mock.search_traces.return_value = [sample_trace_data]
    mock.get_trace.return_value = sample_trace_data
    mock.health_check.return_value = AsyncMock(
        status="healthy",
        backend="jaeger",
        url="http://localhost:16686",
        service_count=3,
    )
    return mock
