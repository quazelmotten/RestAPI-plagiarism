"""
Message handler for RabbitMQ.
Wraps task orchestrator to handle incoming messages.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

from worker.services.task_orchestrator import TaskOrchestrator

log = logging.getLogger(__name__)


class MessageHandler:
    """Handles incoming RabbitMQ messages."""
    
    def __init__(self, task_orchestrator: TaskOrchestrator):
        """
        Initialize message handler.
        
        Args:
            task_orchestrator: TaskOrchestrator instance
        """
        self.task_orchestrator = task_orchestrator
    
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
            body: Message body bytes
        """
        log.info(f"Received message, submitting to task orchestrator...")
        try:
            self.task_orchestrator.process_task(
                body=body,
                channel=ch,
                delivery_tag=method.delivery_tag
            )
        except Exception as e:
            log.error(f"Error in message handler: {e}")
            import traceback
            log.error(traceback.format_exc())
            raise  # Re-raise to let worker handle nack
