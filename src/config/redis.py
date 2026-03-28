"""
Redis configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisConfig(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str | None = Field(default=None)
    use_ssl: bool = Field(default=False)
    ttl: int = Field(default=86400, description="Default TTL for cached items (seconds)")
    fingerprint_ttl: int = Field(default=604800, description="TTL for fingerprint cache (seconds)")
    maxmemory: str = Field(default="512mb", description="Max memory for Redis")

    @property
    def url(self) -> str:
        """Generate Redis URL."""
        scheme = "rediss" if self.use_ssl else "redis"
        return f"{scheme}://{self.host}:{self.port}/{self.db}"
