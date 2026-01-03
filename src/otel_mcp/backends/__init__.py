"""Backends package - trace storage backend implementations."""

from otel_mcp.backends.base import BaseBackend
from otel_mcp.backends.jaeger import JaegerBackend

__all__ = ["BaseBackend", "JaegerBackend"]
