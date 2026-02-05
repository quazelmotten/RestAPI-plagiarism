from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: str = Field(default="5432", validation_alias="DB_PORT")
    db_name: str = Field(default="appdb", validation_alias="DB_NAME")
    db_user: str = Field(default="appuser", validation_alias="DB_USER")
    db_pass: str = Field(default="password", validation_alias="DB_PASS")

    rmq_host: str = Field(default="localhost", validation_alias="RMQ_HOST")
    rmq_port: int = Field(default=5672, validation_alias="RMQ_PORT")
    rmq_user: str = Field(default="guest", validation_alias="RMQ_USER")
    rmq_password: str = Field(default="guest", validation_alias="RMQ_PASSWORD")

    rmq_queue_exchange: str = Field(default="tasks", validation_alias="RMQ_QUEUE_EXCHANGE")
    rmq_queue_routing_key: str = Field(default="tasks", validation_alias="RMQ_QUEUE_ROUTING_KEY")
    rmq_queue_name: str = Field(default="tasks", validation_alias="RMQ_QUEUE_NAME")
    rmq_queue_dead_letter_exchange: str = Field(
        default="tasks_dlx", validation_alias="RMQ_QUEUE_DEAD_LETTER_EXCHANGE"
    )
    rmq_queue_routing_key_dead_letter: str = Field(
        default="tasks.dead", validation_alias="RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER"
    )
    rmq_queue_dead_letter_name: str = Field(default="tasks_dead", validation_alias="RMQ_QUEUE_DEAD_LETTER_NAME")


settings = Settings()
