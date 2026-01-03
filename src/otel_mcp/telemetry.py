"""OpenTelemetry self-instrumentation setup."""

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def setup_telemetry(service_name: str = "jaeger-mcp") -> None:
    """Configure OpenTelemetry tracing for the MCP server.

    Args:
        service_name: Name of this service in traces
    """
    # Check if telemetry is disabled
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        logger.info("OpenTelemetry SDK disabled via OTEL_SDK_DISABLED")
        return

    # Get OTLP endpoint from environment
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    try:
        # Create resource with service info
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "0.1.0",
            }
        )

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        # Instrument httpx for outgoing requests
        HTTPXClientInstrumentor().instrument()

        logger.info(f"OpenTelemetry configured: service={service_name}, endpoint={otlp_endpoint}")

    except Exception as e:
        logger.warning(f"Failed to configure OpenTelemetry: {e}")


def get_tracer(name: str = "jaeger-mcp") -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Name for the tracer

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def traced(name: str | None = None) -> Callable[[F], F]:
    """Decorator to create a span for a function.

    Args:
        name: Optional span name (defaults to function name)

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        tracer = get_tracer()
        span_name = name or func.__name__

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
