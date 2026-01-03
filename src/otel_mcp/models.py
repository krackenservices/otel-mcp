"""Pydantic models for traces, spans, and query parameters."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SpanStatus(str, Enum):
    """Span status codes."""

    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


class SpanKind(str, Enum):
    """Span kind indicating the role of the span."""

    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class SpanEvent(BaseModel):
    """An event that occurred during a span's lifetime."""

    name: str
    timestamp: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanData(BaseModel):
    """Individual span data."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation_name: str
    service_name: str
    start_time: datetime
    duration_ms: float
    status: SpanStatus = SpanStatus.UNSET
    kind: SpanKind = SpanKind.INTERNAL
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)
    has_error: bool = False
    error_message: str | None = None

    @property
    def end_time(self) -> datetime:
        """Calculate end time from start time and duration."""
        return datetime.fromtimestamp(
            self.start_time.timestamp() + (self.duration_ms / 1000),
            tz=self.start_time.tzinfo,
        )


class TraceData(BaseModel):
    """Complete trace data with all spans."""

    trace_id: str
    spans: list[SpanData]
    start_time: datetime
    duration_ms: float
    service_name: str
    root_operation: str
    status: SpanStatus = SpanStatus.OK
    span_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        """Set span count after initialization."""
        self.span_count = len(self.spans)

    @property
    def has_error(self) -> bool:
        """Check if any span in the trace has an error."""
        return any(span.has_error for span in self.spans)


class TraceSummary(BaseModel):
    """Summary of a trace for list views."""

    trace_id: str
    service_name: str
    root_operation: str
    start_time: datetime
    duration_ms: float
    span_count: int
    has_error: bool = False


class TraceQuery(BaseModel):
    """Query parameters for searching traces."""

    service_name: str | None = None
    operation_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    tags: dict[str, str] | None = None
    has_error: bool | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str  # "healthy" or "unhealthy"
    backend: str
    url: str
    service_count: int | None = None
    error: str | None = None


class ServiceStats(BaseModel):
    """Statistics for a service or operation."""

    name: str
    request_count: int
    error_count: int
    error_rate: float
    avg_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
