"""
Worker configuration.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerConfig(BaseSettings):
    """Worker process settings."""

    model_config = SettingsConfigDict(
        env_prefix="WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    concurrency: int = Field(default=4, validation_alias="WORKER_CONCURRENCY")
    prefetch_count: int = Field(default=1, validation_alias="WORKER_PREFETCH_COUNT")

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Worker concurrency must be positive")
        if v > 64:  # Reasonable upper limit
            raise ValueError("Worker concurrency too high (max 64)")
        return v
