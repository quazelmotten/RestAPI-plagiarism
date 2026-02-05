"""
Production-ready configuration management for Plagiarism Detection API.
All settings loaded from environment variables with validation.
"""

import os
import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # =============================================================================
    # DATABASE CONFIGURATION
    # =============================================================================
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(default="plagiarism_db", validation_alias="DB_NAME")
    db_user: str = Field(default="plagiarism_user", validation_alias="DB_USER")
    db_pass: str = Field(validation_alias="DB_PASS")
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    
    # =============================================================================
    # RABBITMQ CONFIGURATION
    # =============================================================================
    rmq_host: str = Field(default="localhost", validation_alias="RMQ_HOST")
    rmq_port: int = Field(default=5672, validation_alias="RMQ_PORT")
    rmq_user: str = Field(default="plagiarism_mq_user", validation_alias="RMQ_USER")
    rmq_pass: str = Field(validation_alias="RMQ_PASS")
    rmq_queue_exchange: str = Field(default="plagiarism", validation_alias="RMQ_QUEUE_EXCHANGE")
    rmq_queue_routing_key: str = Field(default="plagiarism", validation_alias="RMQ_QUEUE_ROUTING_KEY")
    rmq_queue_name: str = Field(default="plagiarism_queue", validation_alias="RMQ_QUEUE_NAME")
    rmq_queue_dead_letter_exchange: str = Field(default="plagiarism_dlx", validation_alias="RMQ_QUEUE_DEAD_LETTER_EXCHANGE")
    rmq_queue_routing_key_dead_letter: str = Field(default="plagiarism.dead", validation_alias="RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER")
    rmq_queue_dead_letter_name: str = Field(default="plagiarism_dead", validation_alias="RMQ_QUEUE_DEAD_LETTER_NAME")
    
    # =============================================================================
    # API CONFIGURATION
    # =============================================================================
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    api_workers: int = Field(default=1, validation_alias="API_WORKERS")
    secret_key: str = Field(validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    
    # =============================================================================
    # PLAGIARISM SETTINGS
    # =============================================================================
    default_plagiarism_threshold: float = Field(default=0.75, validation_alias="DEFAULT_PLAGIARISM_THRESHOLD")
    supported_languages: str = Field(default="python,java,cpp,c,javascript", validation_alias="SUPPORTED_LANGUAGES")
    max_file_size: int = Field(default=1048576, validation_alias="MAX_FILE_SIZE")
    max_files_per_batch: int = Field(default=100, validation_alias="MAX_FILES_PER_BATCH")
    
    # =============================================================================
    # WORKER CONFIGURATION
    # =============================================================================
    worker_concurrency: int = Field(default=4, validation_alias="WORKER_CONCURRENCY")
    worker_prefetch_count: int = Field(default=1, validation_alias="WORKER_PREFETCH_COUNT")
    
    # =============================================================================
    # LOGGING
    # =============================================================================
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")
    
    # =============================================================================
    # MONITORING
    # =============================================================================
    sentry_dsn: Optional[str] = Field(default=None, validation_alias="SENTRY_DSN")
    metrics_endpoint: Optional[str] = Field(default=None, validation_alias="METRICS_ENDPOINT")
    
    # =============================================================================
    # VALIDATORS
    # =============================================================================
    
    @field_validator("db_pass")
    @classmethod
    def validate_db_password(cls, v: str) -> str:
        """Ensure database password is strong enough."""
        if len(v) < 16:
            raise ValueError("Database password must be at least 16 characters")
        return v
    
    @field_validator("rmq_pass")
    @classmethod
    def validate_rmq_password(cls, v: str) -> str:
        """Ensure RabbitMQ password is strong enough."""
        if len(v) < 16:
            raise ValueError("RabbitMQ password must be at least 16 characters")
        return v
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is valid."""
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v.lower()
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is strong enough."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        return v
    
    @field_validator("default_plagiarism_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Ensure threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()
    
    # =============================================================================
    # PROPERTIES
    # =============================================================================
    
    @property
    def db_async_url(self) -> str:
        """Generate async PostgreSQL URL."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def db_sync_url(self) -> str:
        """Generate sync PostgreSQL URL."""
        return f"postgresql+psycopg2://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def rmq_url(self) -> str:
        """Generate RabbitMQ AMQP URL."""
        return f"amqp://{self.rmq_user}:{self.rmq_pass}@{self.rmq_host}:{self.rmq_port}/"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def supported_languages_list(self) -> List[str]:
        """Parse supported languages into list."""
        return [lang.strip().lower() for lang in self.supported_languages.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        return Settings()
    except ValidationError as e:
        print("❌ Configuration Error:")
        print("=" * 60)
        for error in e.errors():
            field = " -> ".join(str(x) for x in error['loc'])
            print(f"  • {field}: {error['msg']}")
        print("=" * 60)
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("Copy .env.example to .env and fill in your values.")
        raise SystemExit(1)


# Global settings instance
settings = get_settings()
