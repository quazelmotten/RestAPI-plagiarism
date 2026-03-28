"""
WebSocket connection manager for real-time task progress updates.

Subscribes to Redis Pub/Sub channels published by the worker and broadcasts
progress messages to all connected WebSocket clients per task.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from starlette.websockets import WebSocket, WebSocketState

from config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and Redis Pub/Sub for task progress."""

    MAX_TOTAL_CONNECTIONS = 100
    MAX_CONNECTIONS_PER_TASK = 10

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._redis: aioredis.Redis | None = None
        self._subscriber_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the manager and its background Redis subscriber."""
        logger.info("Starting WebSocket connection manager")
        self._running = True
        self._redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        await self._redis.ping()
        logger.info(
            "Redis subscriber connected (%s:%s/%s)",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )
        self._subscriber_task = asyncio.create_task(self._subscribe_to_redis())

    async def _subscribe_to_redis(self):
        """Subscribe to Redis channels matching task:*:progress and broadcast to WebSocket clients."""
        pubsub = self._redis.pubsub()
        try:
            await pubsub.psubscribe("task:*:progress")
            logger.info("Subscribed to Redis pattern: task:*:progress")

            while self._running:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.01)
                    if message is None:
                        continue

                    if message["type"] not in ("message", "pmessage"):
                        continue

                    channel = message.get("channel", "")
                    data = json.loads(message["data"])
                    parts = channel.split(":")
                    if len(parts) >= 2:
                        task_id = parts[1]
                        await self._broadcast_to_task(task_id, data)
                        logger.debug(
                            "Broadcast progress for task %s to %d clients",
                            task_id,
                            len(self._connections.get(task_id, set())),
                        )

                except TimeoutError:
                    continue
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in Redis message: %s", e)
                except Exception as e:
                    logger.error("Error in Redis subscriber loop: %s", e, exc_info=True)
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Redis subscriber task cancelled")
        finally:
            await pubsub.aclose()

    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a WebSocket connection and register it for a task."""
        total = sum(len(s) for s in self._connections.values())
        if total >= self.MAX_TOTAL_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            logger.warning("WebSocket rejected — global limit reached (%d)", total)
            return

        task_conns = self._connections.get(task_id, set())
        if len(task_conns) >= self.MAX_CONNECTIONS_PER_TASK:
            await websocket.close(code=1013, reason="Too many connections for this task")
            logger.warning("WebSocket rejected — per-task limit reached for %s", task_id)
            return

        await websocket.accept()
        self._connections.setdefault(task_id, set()).add(websocket)
        logger.info(
            "WebSocket connected for task %s from %s (total: %d)",
            task_id,
            websocket.client.host if websocket.client else "unknown",
            self._count_connections(task_id),
        )

    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection."""
        if task_id in self._connections:
            self._connections[task_id].discard(websocket)
            if not self._connections[task_id]:
                del self._connections[task_id]
        logger.info(
            "WebSocket disconnected for task %s (remaining: %d)",
            task_id,
            self._count_connections(task_id),
        )

    async def _broadcast_to_task(self, task_id: str, data: dict):
        """Send data to all connected clients for a task."""
        connections = self._connections.get(task_id, set())
        if not connections:
            return

        closed = set()
        for ws in connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(data)
            except Exception:
                closed.add(ws)

        for ws in closed:
            connections.discard(ws)
        if not connections:
            self._connections.pop(task_id, None)

    def _count_connections(self, task_id: str) -> int:
        return len(self._connections.get(task_id, set()))

    async def stop(self):
        """Stop the subscriber and close connections."""
        self._running = False
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        logger.info("WebSocket connection manager stopped")


_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the singleton connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
