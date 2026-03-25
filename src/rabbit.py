import aio_pika
import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

_connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
_channel: Optional[aio_pika.abc.AbstractChannel] = None
_exchange: Optional[aio_pika.abc.AbstractExchange] = None


def get_rabbit_url():
    return (
        f"amqp://{settings.rmq_user}:{settings.rmq_pass}"
        f"@{settings.rmq_host}:{settings.rmq_port}/"
    )


async def connect():
    """Establish a shared RabbitMQ connection, channel, and exchange."""
    global _connection, _channel, _exchange
    if _connection and not _connection.is_closed:
        return
    _connection = await aio_pika.connect_robust(get_rabbit_url())
    _channel = await _connection.channel()
    _exchange = await _channel.declare_exchange(
        settings.rmq_queue_exchange,
        aio_pika.ExchangeType.DIRECT,
        durable=True,
    )
    logger.info("RabbitMQ connection established")


async def disconnect():
    """Gracefully close the shared RabbitMQ connection."""
    global _connection, _channel, _exchange
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None
    _channel = None
    _exchange = None
    logger.info("RabbitMQ connection closed")


async def publish_message(queue: str, message: dict):
    """Publish a message using the shared connection."""
    global _exchange
    if _exchange is None or (_connection and _connection.is_closed):
        await connect()
    await _exchange.publish(
        aio_pika.Message(body=json.dumps(message).encode()),
        routing_key=settings.rmq_queue_routing_key,
    )


async def get_async_channel() -> aio_pika.Channel:
    """Get a channel from the shared connection."""
    global _connection, _channel
    if _connection is None or _connection.is_closed:
        await connect()
    return _channel
