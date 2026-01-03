"""Jaeger backend implementation for querying OpenTelemetry traces."""

import logging
from datetime import UTC, datetime
from typing import Any

from otel_mcp.backends.base import BaseBackend
from otel_mcp.models import (
    HealthCheckResponse,
    SpanData,
    SpanEvent,
    SpanKind,
    SpanStatus,
    TraceData,
    TraceQuery,
)

logger = logging.getLogger(__name__)


class JaegerBackend(BaseBackend):
    """Jaeger Query API backend implementation."""

    def _create_headers(self) -> dict[str, str]:
        """Create headers for Jaeger API requests."""
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def list_services(self) -> list[str]:
        """List all services from Jaeger.

        Returns:
            List of service names
        """
        logger.debug("Listing services")

        response = await self.client.get("/api/services")
        response.raise_for_status()

        data = response.json()
        services_raw = data.get("data", [])
        return [str(s) for s in services_raw]

    async def get_operations(self, service_name: str) -> list[str]:
        """Get operations for a service from Jaeger.

        Args:
            service_name: Service name

        Returns:
            List of operation names
        """
        logger.debug(f"Getting operations for service: {service_name}")

        response = await self.client.get(f"/api/services/{service_name}/operations")
        response.raise_for_status()

        data = response.json()
        return [str(op) for op in data.get("data", [])]

    async def search_traces(self, query: TraceQuery) -> list[TraceData]:
        """Search for traces using Jaeger Query API.

        Args:
            query: Trace query parameters

        Returns:
            List of matching traces

        Raises:
            ValueError: If service_name is not provided
        """
        if not query.service_name:
            raise ValueError(
                "Jaeger backend requires 'service_name' parameter. "
                "Use list_services() to see available services."
            )

        params = self._build_query_params(query)
        logger.debug(f"Searching traces with params: {params}")

        response = await self.client.get("/api/traces", params=params)
        response.raise_for_status()

        data = response.json()
        traces = []

        for trace_data in data.get("data", []):
            trace = self._parse_jaeger_trace(trace_data)
            if trace:
                traces.append(trace)

        return traces

    async def get_trace(self, trace_id: str) -> TraceData:
        """Get a specific trace by ID from Jaeger.

        Args:
            trace_id: Trace identifier

        Returns:
            Complete trace data
        """
        logger.debug(f"Fetching trace: {trace_id}")

        response = await self.client.get(f"/api/traces/{trace_id}")
        response.raise_for_status()

        data = response.json()

        if not data.get("data") or len(data["data"]) == 0:
            raise ValueError(f"Trace not found: {trace_id}")

        trace = self._parse_jaeger_trace(data["data"][0])
        if not trace:
            raise ValueError(f"Failed to parse trace: {trace_id}")

        return trace

    async def health_check(self) -> HealthCheckResponse:
        """Check Jaeger backend health.

        Returns:
            Health status information
        """
        logger.debug("Checking backend health")

        try:
            services = await self.list_services()
            return HealthCheckResponse(
                status="healthy",
                backend="jaeger",
                url=self.url,
                service_count=len(services),
            )
        except Exception as e:
            return HealthCheckResponse(
                status="unhealthy",
                backend="jaeger",
                url=self.url,
                error=str(e),
            )

    def _build_query_params(self, query: TraceQuery) -> dict[str, Any]:
        """Build Jaeger API query parameters from TraceQuery."""
        params: dict[str, Any] = {
            "service": query.service_name,
            "limit": query.limit,
        }

        if query.operation_name:
            params["operation"] = query.operation_name

        if query.start_time:
            # Jaeger uses microseconds
            params["start"] = int(query.start_time.timestamp() * 1_000_000)

        if query.end_time:
            params["end"] = int(query.end_time.timestamp() * 1_000_000)

        if query.min_duration_ms:
            # Jaeger uses microseconds for duration
            params["minDuration"] = f"{query.min_duration_ms * 1000}us"

        if query.max_duration_ms:
            params["maxDuration"] = f"{query.max_duration_ms * 1000}us"

        if query.tags:
            # Jaeger expects tags as JSON
            import json

            params["tags"] = json.dumps(query.tags)

        return params

    def _parse_jaeger_trace(self, trace_data: dict[str, Any]) -> TraceData | None:
        """Parse Jaeger trace JSON format to TraceData model."""
        try:
            trace_id = trace_data.get("traceID")
            if not trace_id:
                logger.warning("Trace missing traceID")
                return None

            spans_data = trace_data.get("spans", [])
            if not spans_data:
                logger.warning(f"Trace {trace_id} has no spans")
                return None

            processes = trace_data.get("processes", {})

            spans: list[SpanData] = []
            for span_data in spans_data:
                span = self._parse_jaeger_span(span_data, processes)
                if span:
                    spans.append(span)

            if not spans:
                logger.warning(f"No valid spans in trace {trace_id}")
                return None

            # Find root span (no parent)
            root_spans = [s for s in spans if not s.parent_span_id]
            root_span = root_spans[0] if root_spans else spans[0]

            # Calculate trace duration
            start_times = [s.start_time for s in spans]
            end_times = [s.end_time for s in spans]
            trace_start = min(start_times)
            trace_end = max(end_times)
            trace_duration_ms = (trace_end - trace_start).total_seconds() * 1000

            # Determine overall status
            trace_status = SpanStatus.OK
            if any(span.has_error for span in spans):
                trace_status = SpanStatus.ERROR

            return TraceData(
                trace_id=trace_id,
                spans=spans,
                start_time=trace_start,
                duration_ms=trace_duration_ms,
                service_name=root_span.service_name,
                root_operation=root_span.operation_name,
                status=trace_status,
            )

        except Exception as e:
            logger.error(f"Error parsing trace: {e}")
            return None

    def _parse_jaeger_span(
        self, span_data: dict[str, Any], processes: dict[str, Any]
    ) -> SpanData | None:
        """Parse Jaeger span JSON to SpanData model."""
        try:
            trace_id = span_data.get("traceID")
            span_id = span_data.get("spanID")
            operation_name = span_data.get("operationName")

            if not all([trace_id, span_id, operation_name]):
                logger.warning("Span missing required fields")
                return None

            # Parse timestamps (Jaeger uses microseconds)
            start_time_us = span_data.get("startTime", 0)
            duration_us = span_data.get("duration", 0)

            start_time = datetime.fromtimestamp(start_time_us / 1_000_000, tz=UTC)
            duration_ms = duration_us / 1000

            # Get process/service info
            process_id = span_data.get("processID", "")
            process = processes.get(process_id, {})
            service_name = process.get("serviceName", "unknown")

            # Parse parent span ID
            references = span_data.get("references", [])
            parent_span_id = None
            for ref in references:
                if ref.get("refType") == "CHILD_OF":
                    parent_span_id = ref.get("spanID")
                    break

            # Parse tags into attributes
            tags = span_data.get("tags", [])
            attributes: dict[str, Any] = {}
            has_error = False
            error_message = None
            span_kind = SpanKind.INTERNAL

            for tag in tags:
                key = tag.get("key", "")
                value = tag.get("value")

                if key == "error" and value:
                    has_error = True
                elif key == "otel.status_code" and value == "ERROR":
                    has_error = True
                elif key == "error.message":
                    error_message = str(value)
                elif key == "span.kind":
                    kind_map = {
                        "server": SpanKind.SERVER,
                        "client": SpanKind.CLIENT,
                        "producer": SpanKind.PRODUCER,
                        "consumer": SpanKind.CONSUMER,
                    }
                    span_kind = kind_map.get(str(value).lower(), SpanKind.INTERNAL)
                else:
                    attributes[key] = value

            # Parse events/logs
            logs = span_data.get("logs", [])
            events: list[SpanEvent] = []
            for log in logs:
                log_ts = log.get("timestamp", 0)
                log_fields = log.get("fields", [])
                event_attrs: dict[str, Any] = {}
                event_name = "log"

                for field in log_fields:
                    field_key = field.get("key", "")
                    field_value = field.get("value")
                    if field_key == "event":
                        event_name = str(field_value)
                    elif field_key == "message" and has_error and not error_message:
                        error_message = str(field_value)
                    else:
                        event_attrs[field_key] = field_value

                events.append(
                    SpanEvent(
                        name=event_name,
                        timestamp=datetime.fromtimestamp(log_ts / 1_000_000, tz=UTC),
                        attributes=event_attrs,
                    )
                )

            return SpanData(
                trace_id=str(trace_id),
                span_id=str(span_id),
                parent_span_id=parent_span_id,
                operation_name=str(operation_name),
                service_name=service_name,
                start_time=start_time,
                duration_ms=duration_ms,
                status=SpanStatus.ERROR if has_error else SpanStatus.OK,
                kind=span_kind,
                attributes=attributes,
                events=events,
                has_error=has_error,
                error_message=error_message,
            )

        except Exception as e:
            logger.error(f"Error parsing span: {e}")
            return None
