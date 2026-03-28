"""
Logging configuration.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingConfig(BaseSettings):
    """Logging settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    format: str = Field(default="json", validation_alias="LOG_FORMAT")

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()

    @property
    def format_type(self) -> str:
        """Get format type (json or plain)."""
        return "json" if self.format.lower() == "json" else "plain"
