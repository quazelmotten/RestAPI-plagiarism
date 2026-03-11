"""
Worker lifecycle management.
Handles setup, teardown, and main execution loop.
"""

import logging
import signal
import sys
import time
from typing import Optional, TYPE_CHECKING

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from config import settings
from redis_cache import connect_cache
from rabbit import get_connection, create_channel

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel

log = logging.getLogger(__name__)

DEFAULT_LOG_FORMAT = "%(module)s:%(lineno)d %(levelname)-6s - %(message)s"


class WorkerLifecycle:
    """Manages worker lifecycle and execution."""
    
    def __init__(
        self,
        message_handler,
        worker_concurrency: Optional[int] = None,
        log_level: Optional[int] = None
    ):
        """
        Initialize worker lifecycle.
        
        Args:
            message_handler: Handler for processing messages (has on_message method)
            worker_concurrency: Number of concurrent workers (defaults to settings.worker_concurrency)
            log_level: Logging level (defaults to settings.log_level)
        """
        self.message_handler = message_handler
        self.worker_concurrency = worker_concurrency or getattr(settings, 'worker_concurrency', 4)
        self.log_level = log_level or self._parse_log_level(getattr(settings, 'log_level', 'INFO'))
        
        self.executor: Optional[ThreadPoolExecutor] = None
        self.analysis_executor: Optional[ProcessPoolExecutor] = None
        self.connection = None
        self.shutting_down = False
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _parse_log_level(self, level_str: str) -> int:
        """Parse log level string to logging constant."""
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(level_str.upper(), logging.INFO)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        self.shutting_down = True
        log.info("Shutdown signal received, stopping worker...")
    
    def configure_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=self.log_level,
            datefmt="%Y-%m-%d %H:%M:%S",
            format=DEFAULT_LOG_FORMAT,
        )
        logging.getLogger("pika").setLevel(logging.WARNING)
        log.info(f"Logging configured at {logging.getLevelName(self.log_level)}")
    
    def initialize(self) -> bool:
        """
        Initialize worker components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.configure_logging()
        
        # Connect to Redis cache
        log.info("Connecting to Redis cache...")
        redis_connected = connect_cache()
        if redis_connected:
            log.info("Redis cache connected and ready")
        else:
            log.warning("Redis cache unavailable, running without caching")
        
        # Create executors
        self.executor = ThreadPoolExecutor(max_workers=self.worker_concurrency)
        self.analysis_executor = ProcessPoolExecutor(max_workers=self.worker_concurrency)
        log.info(f"Thread pool executor started with {self.worker_concurrency} workers")
        log.info(f"Process pool executor started with {self.worker_concurrency} workers (for analysis)")
        
        return True
    
    def run(self) -> None:
        """Main worker execution loop."""
        try:
            if not self.initialize():
                log.error("Failed to initialize worker")
                return
            
            max_retries = 30
            retry_delay = 2
            
            for attempt in range(max_retries):
                if self.shutting_down:
                    log.info("Shutdown requested, exiting retry loop")
                    break
                
                try:
                    log.info(f"Connecting to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
                    self.connection = get_connection()
                    with self.connection:
                        with self.connection.channel() as channel:
                            create_channel(channel)
                            log.info("Successfully connected to RabbitMQ")
                            self._consume_messages(channel)
                    # If consume_messages returns normally (e.g., due to shutdown), exit retry loop
                    break
                except Exception as e:
                    log.warning(f"Failed to connect to RabbitMQ: {e}")
                    if attempt < max_retries - 1 and not self.shutting_down:
                        log.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        if self.shutting_down:
                            log.info("Shutdown requested, not retrying")
                        else:
                            log.error("Max retries reached. Exiting.")
                        raise
        finally:
            self.shutdown()
    
    def _consume_messages(self, channel: "BlockingChannel") -> None:
        """
        Start consuming messages from RabbitMQ.
        
        Args:
            channel: RabbitMQ channel
        """
        log.info("[X] Waiting for plagiarism tasks...")
        channel.basic_qos(prefetch_count=getattr(settings, 'worker_prefetch_count', 1))
        channel.basic_consume(
            queue=settings.rmq_queue_name,
            on_message_callback=self._on_message_wrapper,
        )
        # Use a loop to check for shutdown signals
        while not self.shutting_down:
            try:
                # Process events for up to 1 second, allowing heartbeat and signal checks
                channel.connection.process_data_events(time_limit=1)
            except Exception as e:
                log.error(f"Error processing data events: {e}")
                break
        log.info("Stopped consuming messages")
    
    def _on_message_wrapper(
        self,
        ch: "BlockingChannel",
        method,
        properties,
        body: bytes
    ) -> None:
        """
        Wrapper for message handling.
        
        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        log.info(f"Received message, submitting to thread pool...")
        if self.executor:
            self.executor.submit(
                self.message_handler.on_message,
                ch,
                method,
                properties,
                body
            )
        else:
            log.error("Thread pool executor not initialized!")
    
    def shutdown(self) -> None:
        """Shutdown worker gracefully."""
        log.info("Shutting down worker...")
        
        if self.executor:
            self.executor.shutdown(wait=True)
            log.info("Thread pool executor shutdown complete")
        
        if self.analysis_executor:
            self.analysis_executor.shutdown(wait=True)
            log.info("Process pool executor shutdown complete")
        
        if self.connection and self.connection.is_open:
            try:
                self.connection.close()
            except Exception as e:
                log.warning(f"Error closing RabbitMQ connection: {e}")
        
        log.info("Worker shutdown complete")
