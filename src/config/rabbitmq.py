"""
RabbitMQ message broker configuration.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQConfig(BaseSettings):
    """RabbitMQ connection settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(default="localhost", validation_alias="RMQ_HOST")
    port: int = Field(default=5672, validation_alias="RMQ_PORT")
    user: str = Field(default="plagiarism_mq_user", validation_alias="RMQ_USER")
    password: str = Field(validation_alias="RMQ_PASS")

    # Queue configuration
    queue_exchange: str = Field(default="plagiarism", validation_alias="RMQ_QUEUE_EXCHANGE")
    queue_routing_key: str = Field(default="plagiarism", validation_alias="RMQ_QUEUE_ROUTING_KEY")
    queue_name: str = Field(default="plagiarism_queue", validation_alias="RMQ_QUEUE_NAME")

    # Dead letter queue configuration
    dead_letter_exchange: str = Field(
        default="plagiarism_dlx", validation_alias="RMQ_QUEUE_DEAD_LETTER_EXCHANGE"
    )
    dead_letter_routing_key: str = Field(
        default="plagiarism.dead", validation_alias="RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER"
    )
    dead_letter_queue_name: str = Field(
        default="plagiarism_dead", validation_alias="RMQ_QUEUE_DEAD_LETTER_NAME"
    )

    @property
    def url(self) -> str:
        """Generate RabbitMQ AMQP URL."""
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"
