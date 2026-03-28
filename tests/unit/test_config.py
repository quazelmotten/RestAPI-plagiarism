"""
Tests for configuration system.
"""

import pytest
from pydantic import ValidationError

from config import AppConfig, DatabaseConfig, RabbitMQConfig, RedisConfig, Settings, get_settings


def test_settings_can_be_instantiated():
    """Test that Settings can be instantiated from environment."""
    # This tests that all configs are properly composed
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

    # App properties
    assert settings.app_name == settings.app.name
    assert settings.app_version == settings.app.version
    assert settings.environment == settings.app.environment.value
    assert settings.api_host == settings.app.host
    assert settings.api_port == settings.app.port
    assert settings.api_workers == settings.app.workers
    assert settings.cors_origins == settings.app.cors_origins
    assert settings.cors_origins_list == settings.app.cors_origins_list

    # Database properties
    assert settings.db_sync_url == settings.database.sync_url
    assert settings.db_async_url == settings.database.async_url

    # RabbitMQ properties
    assert settings.rmq_url == settings.rabbitmq.url

    # Redis properties
    assert settings.redis_url == settings.redis.url

    # Plagiarism properties
    assert settings.default_plagiarism_threshold == settings.plagiarism.default_threshold
    assert settings.supported_languages == settings.plagiarism.supported_languages
    assert settings.max_file_size == settings.plagiarism.max_file_size
    assert settings.max_files_per_batch == settings.plagiarism.max_files_per_batch

    # Rate limit properties
    assert settings.rate_limit_enabled == settings.rate_limit.enabled
    assert settings.rate_limit_requests == settings.rate_limit.requests
    assert settings.rate_limit_window == settings.rate_limit.window

    # Worker properties
    assert settings.worker_concurrency == settings.worker.concurrency
    assert settings.worker_prefetch_count == settings.worker.prefetch_count

    # Logging properties
    assert settings.log_level == settings.logging.level
    assert settings.log_format == settings.logging.format

    # Monitoring properties
    assert settings.sentry_dsn == settings.monitoring.sentry_dsn
    assert settings.metrics_endpoint == settings.monitoring.metrics_endpoint

    # Environment flags
    assert settings.is_production == (settings.app.environment.value == "production")
    assert settings.is_development == (settings.app.environment.value == "development")


def test_app_config_cors_validation():
    """Test CORS origins validation."""
    with pytest.raises(ValidationError):
        AppConfig(cors_origins="")


def test_app_config_subpath_normalized():
    """Test subpath normalization."""
    config = AppConfig(subpath="")
    assert config.subpath_normalized == ""

    config = AppConfig(subpath="/api")
    assert config.subpath_normalized == "/api"

    config = AppConfig(subpath="api/")
    assert config.subpath_normalized == "/api"


def test_database_config_urls():
    """Test database URL generation."""
    config = DatabaseConfig(
        host="db.example.com", port=5432, name="testdb", user="testuser", password="testpass"
    )
    assert config.sync_url == "postgresql+psycopg2://testuser:testpass@db.example.com:5432/testdb"
    assert (
        config.async_url
        == "postgresql+asyncpg://testuser:testpass@db.example.com:5432/testdb?async_fallback=True"
    )


def test_redis_config_url_with_ssl():
    """Test Redis URL generation with SSL."""
    config = RedisConfig(host="redis.example.com", port=6379, db=0, use_ssl=True)
    assert config.url == "rediss://redis.example.com:6379/0"

    config = RedisConfig(host="redis.example.com", port=6379, db=0, use_ssl=False)
    assert config.url == "redis://redis.example.com:6379/0"


def test_rabbitmq_config_url():
    """Test RabbitMQ URL generation."""
    config = RabbitMQConfig(host="mq.example.com", port=5672, user="testuser", password="testpass")
    assert config.url == "amqp://testuser:testpass@mq.example.com:5672/"


def test_rate_limit_validation():
    """Test rate limit validation."""
    with pytest.raises(ValidationError):
        from config import RateLimitConfig

        RateLimitConfig(requests=0)

    with pytest.raises(ValidationError):
        from config import RateLimitConfig

        RateLimitConfig(window=0)


def test_logging_config_validation():
    """Test logging level validation."""
    from config import LoggingConfig

    config = LoggingConfig(level="INFO")
    assert config.level == "INFO"

    with pytest.raises(ValidationError):
        LoggingConfig(level="INVALID")


def test_worker_config_validation():
    """Test worker concurrency validation."""
    from config import WorkerConfig

    with pytest.raises(ValidationError):
        WorkerConfig(concurrency=0)

    with pytest.raises(ValidationError):
        WorkerConfig(concurrency=100)  # too high


def test_settings_caching():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2  # Same instance due to lru_cache


def test_settings_from_different_env_vars(monkeypatch):
    """Test that settings load from environment variables correctly."""
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    # Clear the cache to get fresh settings
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "Test App"
    assert settings.environment == "production"
    assert settings.rate_limit_enabled is False
