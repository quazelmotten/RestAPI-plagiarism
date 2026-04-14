"""
Tests for configuration system.
"""

import os
import pytest
from pydantic import ValidationError

from src.config import (
    AppConfig,
    DatabaseConfig,
    RabbitMQConfig,
    RedisConfig,
    Settings,
    get_settings,
)


def test_settings_can_be_instantiated():
    """Test that Settings can be instantiated from environment."""
    settings = Settings()
    assert settings.app is not None
    assert settings.database is not None
    assert settings.redis is not None
    assert settings.rabbitmq is not None
    assert settings.storage is not None
    assert settings.plagiarism is not None
    assert settings.rate_limit is not None
    assert settings.logging is not None
    assert settings.monitoring is not None
    assert settings.worker is not None


def test_backward_compatible_properties():
    """Test that backward-compatible properties work."""
    settings = Settings()

    assert settings.app_name == settings.app.name
    assert settings.app_version == settings.app.version
    assert settings.environment == settings.app.environment.value
    assert settings.api_host == settings.app.host
    assert settings.api_port == settings.app.port
    assert settings.api_workers == settings.app.workers
    assert settings.cors_origins == settings.app.cors_origins
    assert settings.cors_origins_list == settings.app.cors_origins_list

    assert settings.db_sync_url == settings.database.sync_url
    assert settings.db_async_url == settings.database.async_url
    assert settings.rmq_url == settings.rabbitmq.url
    assert settings.redis_url == settings.redis.url

    assert settings.default_plagiarism_threshold == settings.plagiarism.default_threshold
    assert settings.supported_languages == settings.plagiarism.supported_languages
    assert settings.max_file_size == settings.plagiarism.max_file_size
    assert settings.max_files_per_batch == settings.plagiarism.max_files_per_batch

    assert settings.rate_limit_enabled == settings.rate_limit.enabled
    assert settings.rate_limit_requests == settings.rate_limit.requests
    assert settings.rate_limit_window == settings.rate_limit.window

    assert settings.worker_concurrency == settings.worker.concurrency
    assert settings.worker_prefetch_count == settings.worker.prefetch_count

    assert settings.log_level == settings.logging.level
    assert settings.log_format == settings.logging.format

    assert settings.sentry_dsn == settings.monitoring.sentry_dsn
    assert settings.metrics_endpoint == settings.monitoring.metrics_endpoint

    assert settings.is_production == (settings.app.environment.value == "production")
    assert settings.is_development == (settings.app.environment.value == "development")


def test_app_config_cors_validation(monkeypatch):
    """Test CORS origins validation."""
    monkeypatch.setenv("CORS_ORIGINS", "")
    with pytest.raises(ValidationError):
        AppConfig()


def test_app_config_subpath_normalized():
    """Test subpath normalization behavior."""
    config = AppConfig()
    # With .env SUBPATH=plagitype, subpath_normalized includes it
    assert config.subpath_normalized.startswith("/")


def test_database_config_urls():
    """Test database URL generation from current environment."""
    config = DatabaseConfig()
    assert "postgresql+psycopg2://" in config.sync_url
    assert "postgresql+asyncpg://" in config.async_url
    assert config.host in config.sync_url
    assert str(config.port) in config.sync_url
    assert config.name in config.sync_url
    assert config.user in config.sync_url


def test_redis_config_url_with_ssl():
    """Test Redis URL generation with SSL."""
    config = RedisConfig(host="redis.example.com", port=6379, db=0, use_ssl=True)
    assert config.url == "rediss://redis.example.com:6379/0"

    config = RedisConfig(host="redis.example.com", port=6379, db=0, use_ssl=False)
    assert config.url == "redis://redis.example.com:6379/0"


def test_rabbitmq_config_url():
    """Test RabbitMQ URL generation."""
    config = RabbitMQConfig()
    assert config.url.startswith("amqp://")
    assert config.host in config.url
    assert str(config.port) in config.url
    assert config.user in config.url


def test_rate_limit_validation():
    """Test rate limit config defaults and validation behavior."""
    from src.config import RateLimitConfig

    config = RateLimitConfig()
    assert config.enabled is True
    assert config.requests > 0
    assert config.window > 0


def test_logging_config_validation():
    """Test logging level validation."""
    from src.config import LoggingConfig

    config = LoggingConfig()
    assert config.level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def test_worker_config_validation():
    """Test worker config defaults."""
    from src.config import WorkerConfig

    config = WorkerConfig()
    assert config.concurrency > 0
    assert config.concurrency <= 64
    assert config.prefetch_count >= 1


def test_settings_caching():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2


def test_settings_from_different_env_vars(monkeypatch):
    """Test that settings load from environment variables correctly."""
    # Save original values first
    original_app_name = os.environ.get("APP_NAME")
    original_env = os.environ.get("ENVIRONMENT")
    original_rate_limit = os.environ.get("RATE_LIMIT_ENABLED")

    try:
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.app_name == "Test App"
        assert settings.environment == "production"
        assert settings.rate_limit_enabled is False
    finally:
        # Properly restore original environment values
        for key, original in [
            ("APP_NAME", original_app_name),
            ("ENVIRONMENT", original_env),
            ("RATE_LIMIT_ENABLED", original_rate_limit),
        ]:
            try:
                if original is None:
                    if key in os.environ:
                        del os.environ[key]
                else:
                    os.environ[key] = original
            except KeyError:
                pass
