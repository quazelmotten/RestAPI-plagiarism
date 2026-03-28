"""
Monitoring and metrics configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MonitoringConfig(BaseSettings):
    """Monitoring and observability settings."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    metrics_endpoint: str | None = Field(default="/metrics", validation_alias="METRICS_ENDPOINT")
    enable_profiling: bool = Field(default=False, validation_alias="ENABLE_PROFILING")
