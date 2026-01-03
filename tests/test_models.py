"""Tests for Pydantic models."""

from datetime import UTC, datetime

import pytest

from otel_mcp.models import (
    HealthCheckResponse,
    SpanData,
    SpanKind,
    SpanStatus,
    TraceData,
    TraceQuery,
)


class TestSpanData:
    """Tests for SpanData model."""

    def test_create_span(self) -> None:
        """Test creating a basic span."""
        span = SpanData(
            trace_id="trace123",
            span_id="span456",
            operation_name="test-operation",
            service_name="test-service",
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            duration_ms=100.0,
        )

        assert span.trace_id == "trace123"
        assert span.span_id == "span456"
        assert span.status == SpanStatus.UNSET
        assert span.kind == SpanKind.INTERNAL
        assert span.has_error is False

    def test_span_end_time(self) -> None:
        """Test end_time property calculation."""
        span = SpanData(
            trace_id="trace123",
            span_id="span456",
            operation_name="test-operation",
            service_name="test-service",
            start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            duration_ms=1000.0,  # 1 second
        )

        expected_end = datetime(2024, 1, 1, 0, 0, 1, tzinfo=UTC)
        assert span.end_time == expected_end

    def test_span_with_error(self) -> None:
        """Test creating a span with error."""
        span = SpanData(
            trace_id="trace123",
            span_id="span456",
            operation_name="failed-operation",
            service_name="test-service",
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            duration_ms=50.0,
            status=SpanStatus.ERROR,
            has_error=True,
            error_message="Something went wrong",
        )

        assert span.has_error is True
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "Something went wrong"


class TestTraceData:
    """Tests for TraceData model."""

    @pytest.fixture
    def sample_spans(self) -> list[SpanData]:
        """Create sample spans."""
        return [
            SpanData(
                trace_id="trace123",
                span_id="span1",
                operation_name="root-op",
                service_name="service-a",
                start_time=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
                duration_ms=200.0,
            ),
            SpanData(
                trace_id="trace123",
                span_id="span2",
                parent_span_id="span1",
                operation_name="child-op",
                service_name="service-a",
                start_time=datetime(2024, 1, 1, 0, 0, 0, 50000, tzinfo=UTC),
                duration_ms=100.0,
            ),
        ]

    def test_create_trace(self, sample_spans: list[SpanData]) -> None:
        """Test creating a trace."""
        trace = TraceData(
            trace_id="trace123",
            spans=sample_spans,
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            duration_ms=200.0,
            service_name="service-a",
            root_operation="root-op",
        )

        assert trace.trace_id == "trace123"
        assert trace.span_count == 2
        assert trace.has_error is False

    def test_trace_has_error(self) -> None:
        """Test trace has_error property."""
        spans = [
            SpanData(
                trace_id="trace123",
                span_id="span1",
                operation_name="op",
                service_name="svc",
                start_time=datetime(2024, 1, 1, tzinfo=UTC),
                duration_ms=100.0,
                has_error=True,
            ),
        ]

        trace = TraceData(
            trace_id="trace123",
            spans=spans,
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            duration_ms=100.0,
            service_name="svc",
            root_operation="op",
        )

        assert trace.has_error is True


class TestTraceQuery:
    """Tests for TraceQuery model."""

    def test_default_query(self) -> None:
        """Test default query parameters."""
        query = TraceQuery()

        assert query.service_name is None
        assert query.limit == 100

    def test_query_with_params(self) -> None:
        """Test query with custom parameters."""
        query = TraceQuery(
            service_name="my-service",
            operation_name="GET /api",
            min_duration_ms=100,
            max_duration_ms=5000,
            has_error=True,
            limit=50,
        )

        assert query.service_name == "my-service"
        assert query.operation_name == "GET /api"
        assert query.min_duration_ms == 100
        assert query.limit == 50

    def test_query_limit_validation(self) -> None:
        """Test limit validation."""
        with pytest.raises(ValueError):
            TraceQuery(limit=0)

        with pytest.raises(ValueError):
            TraceQuery(limit=1001)


class TestHealthCheckResponse:
    """Tests for HealthCheckResponse model."""

    def test_healthy_response(self) -> None:
        """Test healthy response."""
        response = HealthCheckResponse(
            status="healthy",
            backend="jaeger",
            url="http://localhost:16686",
            service_count=5,
        )

        assert response.status == "healthy"
        assert response.error is None

    def test_unhealthy_response(self) -> None:
        """Test unhealthy response."""
        response = HealthCheckResponse(
            status="unhealthy",
            backend="jaeger",
            url="http://localhost:16686",
            error="Connection refused",
        )

        assert response.status == "unhealthy"
        assert response.error == "Connection refused"
