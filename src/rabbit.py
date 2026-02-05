import aio_pika
import json
from config import settings

RABBIT_URL = (
    f"amqp://{settings.rmq_user}:{settings.rmq_password}"
    f"@{settings.rmq_host}:{settings.rmq_port}/"
)

async def get_async_channel() -> aio_pika.Channel:
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()
    return channel

async def publish_message(queue: str, message: dict):
    connection = await aio_pika.connect_robust(RABBIT_URL)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            settings.rmq_queue_exchange,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=settings.rmq_queue_routing_key,
        )
