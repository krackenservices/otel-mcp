"""Configuration module using pydantic-settings."""

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class BackendType(str, Enum):
    """Supported backend types."""

    JAEGER = "jaeger"
    # Future: TEMPO = "tempo", ZIPKIN = "zipkin"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Backend configuration
    backend_type: BackendType = Field(
        default=BackendType.JAEGER,
        description="Type of tracing backend to use",
    )
    jaeger_url: str = Field(
        default="http://localhost:16686",
        description="Jaeger Query API URL",
    )
    jaeger_timeout: float = Field(
        default=30.0,
        description="Request timeout in seconds",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    # API settings
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host",
    )
    api_port: int = Field(
        default=8000,
        description="API server port",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
