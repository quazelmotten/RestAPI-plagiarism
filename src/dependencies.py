"""
Centralized dependency injection functions for FastAPI.
"""

import redis.asyncio as aioredis
from fastapi import Request

from clients.rabbit_client import RabbitMQ
from clients.redis_client import RedisClient
from clients.s3_client import S3Storage
from websocket_manager import ConnectionManager


async def get_s3_storage(request: Request) -> S3Storage:
    """Get S3 storage instance from app state."""
    return request.app.state.s3_storage


async def get_redis_client(request: Request) -> aioredis.Redis:
    """Get the async Redis client instance."""
    redis_client: RedisClient = request.app.state.redis_client
    return redis_client.get_async_client()


async def get_fingerprint_cache(request: Request):
    """Get fingerprint cache from redis client."""
    redis_client: RedisClient = request.app.state.redis_client
    return redis_client.get_fingerprint_cache()


async def get_publisher(request: Request):
    """Get the RabbitMQ publish_message method."""
    rabbitmq: RabbitMQ = request.app.state.rabbitmq
    return rabbitmq.publish_message


async def get_ws_connection_manager(request: Request) -> ConnectionManager:
    """Get the WebSocket connection manager instance."""
    return request.app.state.ws_manager
