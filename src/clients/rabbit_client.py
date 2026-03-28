import json
import logging

import aio_pika

from config import settings

logger = logging.getLogger(__name__)


def get_rabbit_url() -> str:
    """Get RabbitMQ connection URL."""
    return (
        f"amqp://{settings.rmq_user}:{settings.rmq_pass}@{settings.rmq_host}:{settings.rmq_port}/"
    )


class RabbitMQ:
    """RabbitMQ client with connection management."""

    def __init__(self):
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self):
        """Establish RabbitMQ connection, channel, and exchange."""
        if self._connection and not self._connection.is_closed:
            return
        self._connection = await aio_pika.connect_robust(get_rabbit_url())
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            settings.rmq_queue_exchange,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        logger.info("RabbitMQ connection established")

    async def disconnect(self):
        """Gracefully close the RabbitMQ connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None
        logger.info("RabbitMQ connection closed")

    async def publish_message(self, queue: str, message: dict):
        """Publish a message using the connection."""
        if self._exchange is None or (self._connection and self._connection.is_closed):
            await self.connect()
        await self._exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=settings.rmq_queue_routing_key,
        )

    async def get_async_channel(self) -> aio_pika.Channel:
        """Get a channel from the connection."""
        if self._connection is None or self._connection.is_closed:
            await self.connect()
        return self._channel

    @property
    def is_connected(self) -> bool:
        """Check if connection is open."""
        return self._connection is not None and not self._connection.is_closed
