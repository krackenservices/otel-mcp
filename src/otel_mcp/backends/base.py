"""Abstract base backend for trace storage systems."""

from abc import ABC, abstractmethod
from typing import Any

import httpx

from otel_mcp.models import HealthCheckResponse, TraceData, TraceQuery


class BaseBackend(ABC):
    """Abstract interface for trace storage backends."""

    def __init__(self, url: str, api_key: str | None = None, timeout: float = 30.0):
        """Initialize backend with connection parameters.

        Args:
            url: Backend API URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.url,
                headers=self._create_headers(),
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    @abstractmethod
    def _create_headers(self) -> dict[str, str]:
        """Create backend-specific HTTP headers."""
        pass

    @abstractmethod
    async def list_services(self) -> list[str]:
        """List all available services.

        Returns:
            List of service names
        """
        pass

    @abstractmethod
    async def get_operations(self, service_name: str) -> list[str]:
        """Get all operations for a specific service.

        Args:
            service_name: Service name

        Returns:
            List of operation names
        """
        pass

    @abstractmethod
    async def search_traces(self, query: TraceQuery) -> list[TraceData]:
        """Search for traces matching the given query.

        Args:
            query: Trace query parameters

        Returns:
            List of matching traces
        """
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> TraceData:
        """Get a specific trace by ID.

        Args:
            trace_id: Trace identifier

        Returns:
            Complete trace data with all spans
        """
        pass

    @abstractmethod
    async def health_check(self) -> HealthCheckResponse:
        """Check backend health and connectivity.

        Returns:
            Health status information
        """
        pass

    async def close(self) -> None:
        """Close HTTP client connections."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BaseBackend":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
