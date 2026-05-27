"""
File event handler for RabbitMQ file_events queue.
Processes file/upload lifecycle events for downstream reactions.
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

log = logging.getLogger(__name__)


class FileEventHandler:
    """Handles incoming file event messages."""

    def on_message(
        self,
        ch: "BlockingChannel",
        method: "Basic.Deliver",
        properties: "BasicProperties",
        body: bytes,
    ) -> None:
        """
        Handle incoming file event message.

        Currently logs events. Future: webhooks, notifications, etc.
        """
        try:
            message = json.loads(body.decode())
            event_type = message.get("event_type", "unknown")
            event_id = message.get("event_id", "unknown")
            log.info(
                "File event received: %s [id=%s, task=%s, assignment=%s]",
                event_type,
                event_id,
                message.get("task_id"),
                message.get("assignment_id"),
            )
        except json.JSONDecodeError as e:
            log.error("Invalid JSON in file event message: %s", e)
            raise
        except Exception as e:
            log.error("Error processing file event: %s", e)
            raise
