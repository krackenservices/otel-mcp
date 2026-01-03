"""Tests for FastAPI REST API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from otel_mcp.api import app
from otel_mcp.models import HealthCheckResponse, TraceData


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check(self, client: TestClient, mock_backend: AsyncMock) -> None:
        """Test health check endpoint."""
        mock_backend.health_check.return_value = HealthCheckResponse(
            status="healthy",
            backend="jaeger",
            url="http://localhost:16686",
            service_count=3,
        )

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["backend"] == "jaeger"


class TestServicesEndpoint:
    """Tests for /services endpoint."""

    def test_list_services(
        self, client: TestClient, mock_backend: AsyncMock, sample_services: list[str]
    ) -> None:
        """Test listing services."""
        mock_backend.list_services.return_value = sample_services

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/services")

            assert response.status_code == 200
            data = response.json()
            assert data["services"] == sample_services
            assert data["count"] == 3


class TestOperationsEndpoint:
    """Tests for /services/{name}/operations endpoint."""

    def test_list_operations(
        self, client: TestClient, mock_backend: AsyncMock, sample_operations: list[str]
    ) -> None:
        """Test listing operations."""
        mock_backend.get_operations.return_value = sample_operations

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/services/user-service/operations")

            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "user-service"
            assert data["operations"] == sample_operations


class TestTracesEndpoint:
    """Tests for /traces endpoint."""

    def test_search_traces(
        self, client: TestClient, mock_backend: AsyncMock, sample_trace_data: TraceData
    ) -> None:
        """Test searching traces."""
        mock_backend.search_traces.return_value = [sample_trace_data]

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/traces", params={"service_name": "user-service"})

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["traces"][0]["trace_id"] == "abc123"

    def test_search_traces_requires_service_name(self, client: TestClient) -> None:
        """Test that service_name is required."""
        response = client.get("/traces")
        assert response.status_code == 422  # Validation error


class TestTraceByIdEndpoint:
    """Tests for /traces/{trace_id} endpoint."""

    def test_get_trace(
        self, client: TestClient, mock_backend: AsyncMock, sample_trace_data: TraceData
    ) -> None:
        """Test getting a trace by ID."""
        mock_backend.get_trace.return_value = sample_trace_data

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/traces/abc123")

            assert response.status_code == 200
            data = response.json()
            assert data["trace_id"] == "abc123"
            assert "spans" in data

    def test_get_trace_not_found(
        self, client: TestClient, mock_backend: AsyncMock
    ) -> None:
        """Test getting a non-existent trace."""
        mock_backend.get_trace.side_effect = ValueError("Trace not found: xyz")

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/traces/xyz")

            assert response.status_code == 404


class TestErrorTracesEndpoint:
    """Tests for /traces/errors endpoint."""

    def test_find_errors(
        self, client: TestClient, mock_backend: AsyncMock, sample_trace_data: TraceData
    ) -> None:
        """Test finding error traces."""
        mock_backend.search_traces.return_value = [sample_trace_data]

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get("/traces/errors", params={"service_name": "user-service"})

            assert response.status_code == 200
            data = response.json()
            assert "traces" in data


class TestSlowTracesEndpoint:
    """Tests for /traces/slow endpoint."""

    def test_get_slow_traces(
        self, client: TestClient, mock_backend: AsyncMock, sample_trace_data: TraceData
    ) -> None:
        """Test finding slow traces."""
        mock_backend.search_traces.return_value = [sample_trace_data]

        with patch("otel_mcp.api.get_backend", return_value=mock_backend):
            response = client.get(
                "/traces/slow",
                params={"service_name": "user-service", "min_duration_ms": 100},
            )

            assert response.status_code == 200
            data = response.json()
            assert "traces" in data
