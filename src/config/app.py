"""
Application configuration.
"""

from enum import StrEnum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class AppConfig(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    name: str = Field(default="Plagiarism Detection API", validation_alias="APP_NAME")
    version: str = Field(default="1.0.0", validation_alias="APP_VERSION")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, validation_alias="ENVIRONMENT"
    )
    host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    port: int = Field(default=8000, validation_alias="API_PORT")
    workers: int = Field(default=4, validation_alias="API_WORKERS")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    cors_origins_regex: str | None = Field(default=None, validation_alias="CORS_ORIGINS_REGEX")
    cors_headers: list[str] = Field(
        default=["Authorization", "Content-Type"], validation_alias="CORS_HEADERS"
    )

    # Subpath for routing (e.g., /plagitype)
    subpath: str = Field(default="", validation_alias="SUBPATH")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """Ensure CORS origins is non-empty."""
        if not v or not v.strip():
            raise ValueError("CORS_ORIGINS must not be empty")
        return v

    @property
    def subpath_normalized(self) -> str:
        """Return subpath with leading slash, empty string if empty/subpath disabled."""
        if not self.subpath:
            return ""
        return f"/{self.subpath.strip('/')}"
