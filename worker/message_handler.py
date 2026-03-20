"""
Message handler for RabbitMQ.
Adapts incoming messages to the TaskService interface.
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

from worker.services.task_service import TaskService

log = logging.getLogger(__name__)


class MessageHandler:
    """Handles incoming RabbitMQ messages."""
    
    def __init__(self, task_service: TaskService):
        """
        Initialize message handler.

        Args:
            task_service: TaskService instance
        """
        self.task_service = task_service
    
    def on_message(
        self,
        ch: "BlockingChannel",
        method: "Basic.Deliver",
        properties: "BasicProperties",
        body: bytes
    ) -> None:
        """
        Handle incoming message.

        Args:
            ch: RabbitMQ channel
            method: Delivery method
            properties: Message properties
            body: Message body bytes (JSON with task_id, files, language)
        """
        log.info("Received message, processing...")
        try:
            message = json.loads(body.decode())
            task_id = message.get("task_id")
            files = message.get("files", [])
            language = message.get("language", "python")

            if not task_id:
                raise ValueError("Missing task_id in message")
            if not isinstance(files, list) or len(files) < 1:
                raise ValueError("Need at least 1 file")

            log.info(f"[Task {task_id}] Processing {len(files)} files, language={language}")
            self.task_service.process_task(task_id, files, language)

        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in message: {e}")
            raise
        except Exception as e:
            log.error(f"Error processing message: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise  # Re-raise to let worker handle nack
