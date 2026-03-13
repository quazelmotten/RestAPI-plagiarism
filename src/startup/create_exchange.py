import aio_pika
import asyncio
import logging

from aio_pika import ExchangeType

from rabbit import get_rabbit_url
from config import settings

logger = logging.getLogger(__name__)


async def create_queues_and_exchanges():
    connection = await aio_pika.connect_robust(                                                                                                                                                            
    get_rabbit_url(),                                                                                                                                                                                   
    retry_attempts=30,    
    retry_interval=2,                                                                                                                                                  
    timeout=10                                                                                                                                                                                             
    )  
    async with connection:
        channel = await connection.channel()

        main_exchange = await channel.declare_exchange(
            settings.rmq_queue_exchange,
            ExchangeType.DIRECT,
            durable=True,
        )
        main_queue = await channel.declare_queue(
            settings.rmq_queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": settings.rmq_queue_dead_letter_exchange,
                "x-dead-letter-routing-key": (
                    settings.rmq_queue_routing_key_dead_letter
                ),
            },
        )
        await main_queue.bind(main_exchange, routing_key=settings.rmq_queue_routing_key)

        dlx_exchange = await channel.declare_exchange(
            settings.rmq_queue_dead_letter_exchange,
            ExchangeType.DIRECT,
            durable=True,
        )
        dlx_queue = await channel.declare_queue(
            settings.rmq_queue_dead_letter_name, durable=True
        )
        await dlx_queue.bind(
            dlx_exchange, routing_key=settings.rmq_queue_routing_key_dead_letter
        )
        
        logger.info("Successfully connected to RabbitMQ and created exchanges/queues")
        return
