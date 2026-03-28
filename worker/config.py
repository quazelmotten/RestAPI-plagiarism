"""
Configuration management for the plagiarism detection worker.
All settings loaded from environment variables with validation.
"""

from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker settings with validation."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(default="plagiarism_db", validation_alias="DB_NAME")
    db_user: str = Field(default="plagiarism_user", validation_alias="DB_USER")
    db_pass: str = Field(validation_alias="DB_PASS")
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")

    # RabbitMQ
    rmq_host: str = Field(default="localhost", validation_alias="RMQ_HOST")
    rmq_port: int = Field(default=5672, validation_alias="RMQ_PORT")
    rmq_user: str = Field(default="plagiarism_mq_user", validation_alias="RMQ_USER")
    rmq_pass: str = Field(validation_alias="RMQ_PASS")
    rmq_queue_exchange: str = Field(default="plagiarism", validation_alias="RMQ_QUEUE_EXCHANGE")
    rmq_queue_routing_key: str = Field(
        default="plagiarism", validation_alias="RMQ_QUEUE_ROUTING_KEY"
    )
    rmq_queue_name: str = Field(default="plagiarism_queue", validation_alias="RMQ_QUEUE_NAME")
    rmq_queue_dead_letter_exchange: str = Field(
        default="plagiarism_dlx", validation_alias="RMQ_QUEUE_DEAD_LETTER_EXCHANGE"
    )
    rmq_queue_routing_key_dead_letter: str = Field(
        default="plagiarism.dead", validation_alias="RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER"
    )
    rmq_queue_dead_letter_name: str = Field(
        default="plagiarism_dead", validation_alias="RMQ_QUEUE_DEAD_LETTER_NAME"
    )

    # Plagiarism detection
    default_plagiarism_threshold: float = Field(
        default=0.75, validation_alias="DEFAULT_PLAGIARISM_THRESHOLD"
    )
    supported_languages: str = Field(
        default="python,java,cpp,c,javascript", validation_alias="SUPPORTED_LANGUAGES"
    )

    # Worker
    worker_concurrency: int = Field(default=4, validation_alias="WORKER_CONCURRENCY")
    worker_prefetch_count: int = Field(default=1, validation_alias="WORKER_PREFETCH_COUNT")

    # Redis
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: str | None = Field(default=None, validation_alias="REDIS_PASSWORD")
    redis_use_ssl: bool = Field(default=False, validation_alias="REDIS_USE_SSL")
    redis_ttl: int = Field(default=604800, validation_alias="REDIS_TTL")
    redis_fingerprint_ttl: int = Field(default=604800, validation_alias="REDIS_FINGERPRINT_TTL")

    # Inverted index
    inverted_index_min_overlap_threshold: float = Field(
        default=0.15, validation_alias="INVERTED_INDEX_MIN_OVERLAP_THRESHOLD"
    )

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("default_plagiarism_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()

    @property
    def db_sync_url(self) -> str:
        """Generate sync PostgreSQL URL."""
        return f"postgresql+psycopg2://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def rmq_url(self) -> str:
        """Generate RabbitMQ AMQP URL."""
        return f"amqp://{self.rmq_user}:{self.rmq_pass}@{self.rmq_host}:{self.rmq_port}/"

    @property
    def redis_url(self) -> str:
        """Generate Redis URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def supported_languages_list(self) -> list[str]:
        """Parse supported languages into list."""
        return [lang.strip().lower() for lang in self.supported_languages.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        return Settings()
    except ValidationError as e:
        print("Configuration Error:")
        print("=" * 60)
        for error in e.errors():
            field = " -> ".join(str(x) for x in error["loc"])
            print(f"  * {field}: {error['msg']}")
        print("=" * 60)
        print("\nPlease check your .env file and ensure all required variables are set.")
        raise SystemExit(1) from None


# Global settings instance
settings = get_settings()
