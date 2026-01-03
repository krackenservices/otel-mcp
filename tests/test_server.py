"""Tests for MCP server tools."""

import json
from unittest.mock import patch

import pytest

from otel_mcp.backends.base import BaseBackend
from otel_mcp.models import TraceData


class TestListServicesTools:
    """Tests for list_services MCP tool."""

    @pytest.mark.asyncio
    async def test_list_services(
        self, mock_backend, sample_services: list[str]
    ) -> None:
        """Test list_services tool."""
        from otel_mcp import server

        mock_backend.list_services.return_value = sample_services

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            # Access the underlying function via .fn attribute
            result = await server.list_services.fn()

            data = json.loads(result)
            assert data["services"] == sample_services
            assert data["count"] == 3


class TestListOperationsTool:
    """Tests for list_operations MCP tool."""

    @pytest.mark.asyncio
    async def test_list_operations(
        self, mock_backend, sample_operations: list[str]
    ) -> None:
        """Test list_operations tool."""
        from otel_mcp import server

        mock_backend.get_operations.return_value = sample_operations

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.list_operations.fn("user-service")

            data = json.loads(result)
            assert data["service"] == "user-service"
            assert data["operations"] == sample_operations


class TestSearchTracesTool:
    """Tests for search_traces MCP tool."""

    @pytest.mark.asyncio
    async def test_search_traces(
        self, mock_backend, sample_trace_data: TraceData
    ) -> None:
        """Test search_traces tool."""
        from otel_mcp import server

        mock_backend.search_traces.return_value = [sample_trace_data]

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.search_traces.fn(service_name="user-service")

            data = json.loads(result)
            assert data["count"] == 1
            assert data["traces"][0]["trace_id"] == "abc123"


class TestGetTraceTool:
    """Tests for get_trace MCP tool."""

    @pytest.mark.asyncio
    async def test_get_trace(
        self, mock_backend, sample_trace_data: TraceData
    ) -> None:
        """Test get_trace tool."""
        from otel_mcp import server

        mock_backend.get_trace.return_value = sample_trace_data

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.get_trace.fn("abc123")

            data = json.loads(result)
            assert data["trace_id"] == "abc123"
            assert "spans" in data


class TestFindErrorsTool:
    """Tests for find_errors MCP tool."""

    @pytest.mark.asyncio
    async def test_find_errors(
        self, mock_backend, sample_trace_data: TraceData
    ) -> None:
        """Test find_errors tool."""
        from otel_mcp import server

        mock_backend.search_traces.return_value = [sample_trace_data]

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.find_errors.fn(service_name="user-service")

            data = json.loads(result)
            assert "error_traces" in data


class TestGetSlowTracesTool:
    """Tests for get_slow_traces MCP tool."""

    @pytest.mark.asyncio
    async def test_get_slow_traces(
        self, mock_backend, sample_trace_data: TraceData
    ) -> None:
        """Test get_slow_traces tool."""
        from otel_mcp import server

        mock_backend.search_traces.return_value = [sample_trace_data]

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.get_slow_traces.fn(
                service_name="user-service",
                min_duration_ms=100,
            )

            data = json.loads(result)
            assert "slow_traces" in data


class TestGetOperationStatsTool:
    """Tests for get_operation_stats MCP tool."""

    @pytest.mark.asyncio
    async def test_get_operation_stats(
        self, mock_backend, sample_trace_data: TraceData
    ) -> None:
        """Test get_operation_stats tool."""
        from otel_mcp import server

        # Return multiple traces for statistics
        mock_backend.search_traces.return_value = [sample_trace_data] * 10

        async def mock_get_backend_fn() -> BaseBackend:
            return mock_backend

        with patch.object(server, "_get_backend", mock_get_backend_fn):
            result = await server.get_operation_stats.fn(service_name="user-service")

            data = json.loads(result)
            assert data["service"] == "user-service"
            assert "duration_ms" in data
            assert "p50" in data["duration_ms"]
            assert "p95" in data["duration_ms"]


class TestStdioProtocolCompliance:
    """Tests to ensure MCP stdio transport works correctly.

    MCP over stdio requires STDOUT to contain ONLY JSON-RPC protocol messages.
    Any other output (logs, banners, print statements) will break the client.
    """

    def test_logging_configured_to_stderr(self) -> None:
        """Verify that the server's logging is directed to stderr, not stdout.

        This is critical for MCP stdio transport - any output to stdout that
        isn't a JSON-RPC message will corrupt the protocol stream.
        """
        import logging
        import sys

        # Import the server module which configures logging
        from otel_mcp import server  # noqa: F401

        # Get the root logger's handlers
        root_logger = logging.getLogger()

        # Check that any StreamHandlers are pointing to stderr
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                # StreamHandler.stream should be stderr, not stdout
                assert handler.stream is not sys.stdout, (
                    "Logging handler is writing to stdout! "
                    "This will break MCP stdio transport. "
                    "All logs must go to stderr."
                )

    def test_server_module_does_not_print_to_stdout(self) -> None:
        """Verify importing and using the server doesn't pollute stdout."""
        import io
        import sys

        # Capture stdout during import
        captured_stdout = io.StringIO()
        original_stdout = sys.stdout

        try:
            sys.stdout = captured_stdout

            # Force reimport of the server module
            import importlib

            from otel_mcp import server

            importlib.reload(server)

            # Get anything that was printed
            stdout_content = captured_stdout.getvalue()

        finally:
            sys.stdout = original_stdout

        # Stdout should be empty (no banners, logs, or print statements)
        assert stdout_content == "", (
            f"Server module printed to stdout during import: {stdout_content!r}\n"
            "This will break MCP stdio transport. All output must go to stderr."
        )
