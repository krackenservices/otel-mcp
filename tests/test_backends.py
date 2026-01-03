"""Tests for Jaeger backend implementation."""

from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from otel_mcp.backends.jaeger import JaegerBackend
from otel_mcp.models import SpanStatus, TraceQuery


class TestJaegerBackend:
    """Tests for JaegerBackend class."""

    @pytest.fixture
    def backend(self) -> JaegerBackend:
        """Create a JaegerBackend instance for testing."""
        return JaegerBackend(url="http://localhost:16686", timeout=5.0)

    @pytest.mark.asyncio
    async def test_list_services(
        self, backend: JaegerBackend, sample_services: list[str], httpx_mock: HTTPXMock
    ) -> None:
        """Test listing services."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/services",
            json={"data": sample_services},
        )

        services = await backend.list_services()
        assert services == sample_services

    @pytest.mark.asyncio
    async def test_get_operations(
        self, backend: JaegerBackend, sample_operations: list[str], httpx_mock: HTTPXMock
    ) -> None:
        """Test getting operations for a service."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/services/user-service/operations",
            json={"data": sample_operations},
        )

        operations = await backend.get_operations("user-service")
        assert operations == sample_operations

    @pytest.mark.asyncio
    async def test_search_traces_requires_service_name(self, backend: JaegerBackend) -> None:
        """Test that search_traces requires service_name."""
        query = TraceQuery()

        with pytest.raises(ValueError, match="requires 'service_name'"):
            await backend.search_traces(query)

    @pytest.mark.asyncio
    async def test_search_traces(
        self, backend: JaegerBackend, sample_jaeger_trace: dict[str, Any], httpx_mock: HTTPXMock
    ) -> None:
        """Test searching traces."""
        httpx_mock.add_response(
            method="GET",
            json={"data": [sample_jaeger_trace]},
        )

        query = TraceQuery(service_name="user-service", limit=10)
        traces = await backend.search_traces(query)

        assert len(traces) == 1
        assert traces[0].trace_id == "abc123def456"
        assert traces[0].service_name == "user-service"
        assert len(traces[0].spans) == 2

    @pytest.mark.asyncio
    async def test_get_trace(
        self, backend: JaegerBackend, sample_jaeger_trace: dict[str, Any], httpx_mock: HTTPXMock
    ) -> None:
        """Test getting a single trace by ID."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/traces/abc123def456",
            json={"data": [sample_jaeger_trace]},
        )

        trace = await backend.get_trace("abc123def456")

        assert trace.trace_id == "abc123def456"
        assert trace.service_name == "user-service"
        assert trace.root_operation == "HTTP GET /api/users"

    @pytest.mark.asyncio
    async def test_get_trace_not_found(
        self, backend: JaegerBackend, httpx_mock: HTTPXMock
    ) -> None:
        """Test getting a non-existent trace."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/traces/nonexistent",
            json={"data": []},
        )

        with pytest.raises(ValueError, match="Trace not found"):
            await backend.get_trace("nonexistent")

    @pytest.mark.asyncio
    async def test_parse_error_trace(
        self, backend: JaegerBackend, sample_jaeger_error_trace: dict[str, Any], httpx_mock: HTTPXMock
    ) -> None:
        """Test parsing a trace with errors."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/traces/error123",
            json={"data": [sample_jaeger_error_trace]},
        )

        trace = await backend.get_trace("error123")

        assert trace.trace_id == "error123"
        assert trace.status == SpanStatus.ERROR
        assert trace.spans[0].has_error is True
        assert trace.spans[0].error_message == "Connection refused"

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, backend: JaegerBackend, sample_services: list[str], httpx_mock: HTTPXMock
    ) -> None:
        """Test health check when backend is healthy."""
        httpx_mock.add_response(
            url="http://localhost:16686/api/services",
            json={"data": sample_services},
        )

        health = await backend.health_check()

        assert health.status == "healthy"
        assert health.backend == "jaeger"
        assert health.service_count == 3

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(
        self, backend: JaegerBackend, httpx_mock: HTTPXMock
    ) -> None:
        """Test health check when backend is unhealthy."""
        httpx_mock.add_exception(Exception("Connection refused"))

        health = await backend.health_check()

        assert health.status == "unhealthy"
        assert "Connection refused" in health.error  # type: ignore


class TestJaegerBackendQueryParams:
    """Tests for query parameter building."""

    @pytest.fixture
    def backend(self) -> JaegerBackend:
        return JaegerBackend(url="http://localhost:16686")

    def test_build_basic_query(self, backend: JaegerBackend) -> None:
        """Test building basic query parameters."""
        query = TraceQuery(service_name="test-service", limit=50)
        params = backend._build_query_params(query)

        assert params["service"] == "test-service"
        assert params["limit"] == 50

    def test_build_query_with_duration(self, backend: JaegerBackend) -> None:
        """Test building query with duration filters."""
        query = TraceQuery(
            service_name="test-service",
            min_duration_ms=100,
            max_duration_ms=1000,
        )
        params = backend._build_query_params(query)

        assert params["minDuration"] == "100000us"
        assert params["maxDuration"] == "1000000us"

    def test_build_query_with_operation(self, backend: JaegerBackend) -> None:
        """Test building query with operation filter."""
        query = TraceQuery(
            service_name="test-service",
            operation_name="HTTP GET /api",
        )
        params = backend._build_query_params(query)

        assert params["operation"] == "HTTP GET /api"
