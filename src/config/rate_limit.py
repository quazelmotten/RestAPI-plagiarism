"""
Rate limiting configuration.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RateLimitConfig(BaseSettings):
    """Rate limiting settings."""

    model_config = SettingsConfigDict(
        env_prefix="RATE_LIMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=True)
    requests: int = Field(default=100, validation_alias="RATE_LIMIT_REQUESTS")
    window: int = Field(default=60, validation_alias="RATE_LIMIT_WINDOW")

    @field_validator("requests")
    @classmethod
    def validate_requests(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Rate limit requests must be positive")
        return v

    @field_validator("window")
    @classmethod
    def validate_window(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Rate limit window must be positive")
        return v
