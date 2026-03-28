"""
Configuration package - composed from domain-specific configs.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .app import AppConfig
from .database import DatabaseConfig
from .logging import LoggingConfig
from .monitoring import MonitoringConfig
from .plagiarism import PlagiarismConfig
from .rabbitmq import RabbitMQConfig
from .rate_limit import RateLimitConfig
from .redis import RedisConfig
from .storage import StorageConfig
from .worker import WorkerConfig

__all__ = [
    "AppConfig",
    "DatabaseConfig",
    "RedisConfig",
    "RabbitMQConfig",
    "StorageConfig",
    "PlagiarismConfig",
    "RateLimitConfig",
    "LoggingConfig",
    "MonitoringConfig",
    "WorkerConfig",
    "Settings",
    "get_settings",
]


class Settings(BaseSettings):
    """
    Composed settings that aggregates all domain-specific configurations.
    Provides backward-compatible interface to the old monolithic settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Initialize all configs
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    plagiarism: PlagiarismConfig = Field(default_factory=PlagiarismConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)

    # Backward-compatible properties that delegate to specific configs
    @property
    def app_name(self) -> str:
        return self.app.name

    @property
    def app_version(self) -> str:
        return self.app.version

    @property
    def environment(self) -> str:
        return self.app.environment.value

    @property
    def api_host(self) -> str:
        return self.app.host

    @property
    def api_port(self) -> int:
        return self.app.port

    @property
    def api_workers(self) -> int:
        return self.app.workers

    @property
    def cors_origins(self) -> str:
        return self.app.cors_origins

    @property
    def cors_origins_regex(self) -> str | None:
        return self.app.cors_origins_regex

    @property
    def cors_headers(self) -> list[str]:
        return self.app.cors_headers

    @property
    def cors_origins_list(self) -> list[str]:
        return self.app.cors_origins_list

    @property
    def subpath_normalized(self) -> str:
        return self.app.subpath_normalized

    @property
    def db_sync_url(self) -> str:
        return self.database.sync_url

    @property
    def db_async_url(self) -> str:
        return self.database.async_url

    @property
    def rmq_url(self) -> str:
        return self.rabbitmq.url

    @property
    def redis_url(self) -> str:
        return self.redis.url

    @property
    def default_plagiarism_threshold(self) -> float:
        return self.plagiarism.default_threshold

    @property
    def supported_languages(self) -> str:
        return self.plagiarism.supported_languages

    @property
    def supported_languages_list(self) -> list[str]:
        return self.plagiarism.supported_languages_list

    @property
    def max_file_size(self) -> int:
        return self.plagiarism.max_file_size

    @property
    def max_files_per_batch(self) -> int:
        return self.plagiarism.max_files_per_batch

    @property
    def rate_limit_enabled(self) -> bool:
        return self.rate_limit.enabled

    @property
    def rate_limit_requests(self) -> int:
        return self.rate_limit.requests

    @property
    def rate_limit_window(self) -> int:
        return self.rate_limit.window

    @property
    def worker_concurrency(self) -> int:
        return self.worker.concurrency

    @property
    def worker_prefetch_count(self) -> int:
        return self.worker.prefetch_count

    @property
    def log_level(self) -> str:
        return self.logging.level

    @property
    def log_format(self) -> str:
        return self.logging.format

    @property
    def sentry_dsn(self) -> str | None:
        return self.monitoring.sentry_dsn

    @property
    def metrics_endpoint(self) -> str | None:
        return self.monitoring.metrics_endpoint

    @property
    def db_pool_size(self) -> int:
        return self.database.pool_size

    @property
    def db_max_overflow(self) -> int:
        return self.database.max_overflow

    @property
    def db_pool_timeout(self) -> int:
        return self.database.pool_timeout

    @property
    def redis_host(self) -> str:
        return self.redis.host

    @property
    def redis_port(self) -> int:
        return self.redis.port

    @property
    def redis_db(self) -> int:
        return self.redis.db

    @property
    def redis_password(self) -> str | None:
        return self.redis.password

    @property
    def redis_ttl(self) -> int:
        return self.redis.ttl

    @property
    def redis_fingerprint_ttl(self) -> int:
        return self.redis.fingerprint_ttl

    @property
    def rmq_host(self) -> str:
        return self.rabbitmq.host

    @property
    def rmq_port(self) -> int:
        return self.rabbitmq.port

    @property
    def rmq_user(self) -> str:
        return self.rabbitmq.user

    @property
    def rmq_pass(self) -> str:
        return self.rabbitmq.password

    @property
    def rmq_queue_exchange(self) -> str:
        return self.rabbitmq.queue_exchange

    @property
    def rmq_queue_routing_key(self) -> str:
        return self.rabbitmq.queue_routing_key

    @property
    def rmq_queue_name(self) -> str:
        return self.rabbitmq.queue_name

    @property
    def rmq_queue_dead_letter_exchange(self) -> str:
        return self.rabbitmq.dead_letter_exchange

    @property
    def rmq_queue_routing_key_dead_letter(self) -> str:
        return self.rabbitmq.dead_letter_routing_key

    @property
    def rmq_queue_dead_letter_name(self) -> str:
        return self.rabbitmq.dead_letter_queue_name

    @property
    def storage_local_path(self) -> str:
        return self.storage.local_path

    @property
    def bucket_name(self) -> str:
        return self.storage.bucket_name

    @property
    def is_production(self) -> bool:
        return self.app.environment.value == "production"

    @property
    def is_development(self) -> bool:
        return self.app.environment.value == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        return Settings()
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Configuration Error: %s", e)
        raise SystemExit(1) from None


# Global settings instance (backward compatible)
settings = get_settings()
