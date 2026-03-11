"""
Worker lifecycle management using Pika's async SelectConnection.
Handles setup, teardown, and message consumption with proper reconnection.
"""

import logging
import signal
import sys
import time
from typing import Optional, TYPE_CHECKING
import functools

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import pika

from config import settings
from redis_cache import connect_cache
from services.plagiarism_service import PlagiarismService

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties
    from pika.frame import Frame

log = logging.getLogger(__name__)

DEFAULT_LOG_FORMAT = "%(module)s:%(lineno)d %(levelname)-6s - %(message)s"


class AsyncWorker:
    """Asynchronous worker using Pika SelectConnection with auto-reconnect."""

    def __init__(
        self,
        message_handler,
        worker_concurrency: Optional[int] = None,
        log_level: Optional[int] = None,
        analysis_executor: Optional[ProcessPoolExecutor] = None
    ):
        """
        Initialize async worker.

        Args:
            message_handler: Handler for processing messages (has on_message method)
            worker_concurrency: Number of concurrent thread workers
            log_level: Logging level
            analysis_executor: Shared ProcessPoolExecutor for analysis tasks
        """
        self.message_handler = message_handler
        self.worker_concurrency = worker_concurrency or getattr(settings, 'worker_concurrency', 4)
        self.log_level = log_level or self._parse_log_level(getattr(settings, 'log_level', 'INFO'))
        self.analysis_executor = analysis_executor

        # Connection state
        self._connection: Optional[pika.SelectConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._consumer_tag: Optional[str] = None
        self._closing = False
        self._stopping = False
        self._consuming = False
        self._should_reconnect = False

        # Thread pool for message processing
        self.executor: Optional[ThreadPoolExecutor] = None
        self._created_executor = False

        # Timer for reconnection delays
        self._reconnect_delay = 0

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

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

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        log.info("Shutdown signal received")
        self._closing = True
        self.stop()

    def configure_logging(self) -> None:
        """Configure logging."""
        logging.basicConfig(
            level=self.log_level,
            datefmt="%Y-%m-%d %H:%M:%S",
            format=DEFAULT_LOG_FORMAT,
        )
        # Suppress Pika's noisy internal errors
        logging.getLogger("pika").setLevel(logging.CRITICAL)
        log.info(f"Logging configured at {logging.getLevelName(self.log_level)}")

    def initialize(self) -> bool:
        """Initialize worker components."""
        self.configure_logging()

        # Connect to Redis cache
        log.info("Connecting to Redis cache...")
        redis_connected = connect_cache()
        if redis_connected:
            log.info("Redis cache connected and ready")
        else:
            log.warning("Redis cache unavailable, running without caching")

        # Create thread pool
        self.executor = ThreadPoolExecutor(max_workers=self.worker_concurrency)
        log.info(f"Thread pool executor started with {self.worker_concurrency} workers")

        # Use provided analysis_executor or create services without it (will be None in subprocess)
        if self.analysis_executor is None:
            log.info("No analysis executor provided (running in subprocess mode)")
        else:
            log.info("Using shared process pool executor (external)")

        return True

    def run(self) -> None:
        """Main execution loop."""
        try:
            if not self.initialize():
                log.error("Failed to initialize worker")
                return

            self._run_loop()
        finally:
            self.shutdown()

    def _run_loop(self) -> None:
        """Main reconnection loop."""
        while not self._closing:
            try:
                log.info("Connecting to RabbitMQ...")
                self._connection = self._connect()
                # Start the IOLoop - this blocks until connection is closed
                self._connection.ioloop.start()
            except KeyboardInterrupt:
                log.info("Keyboard interrupt received")
                self._closing = True
                break
            except Exception as e:
                log.error(f"Unexpected error in connection loop: {e}")
                import traceback
                log.error(traceback.format_exc())

            if not self._closing:
                # Attempt to reconnect with delay
                delay = self._get_reconnect_delay()
                log.info(f"Reconnecting in {delay} seconds...")
                time.sleep(delay)

    def _connect(self) -> pika.SelectConnection:
        """Create and return a new SelectConnection."""
        parameters = self._get_connection_parameters()
        log.info(f"Connecting to {settings.rmq_host}:{settings.rmq_port}")

        return pika.SelectConnection(
            parameters=parameters,
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed,
        )

    def _get_connection_parameters(self) -> pika.ConnectionParameters:
        """Get RabbitMQ connection parameters."""
        return pika.ConnectionParameters(
            host=settings.rmq_host,
            port=settings.rmq_port,
            credentials=pika.PlainCredentials(
                username=settings.rmq_user,
                password=settings.rmq_pass
            ),
            heartbeat=600,
            blocked_connection_timeout=300,
        )

    def _on_connection_open(self, connection: pika.SelectConnection):
        """Called when connection is established."""
        log.info("Connection opened")
        self._reconnect_delay = 0  # Reset reconnect delay on successful connection
        self._should_reconnect = False  # Clear any previous reconnect flag
        self._open_channel()

    def _on_connection_open_error(self, connection: pika.SelectConnection, err: Exception):
        """Called when connection fails to open."""
        log.error(f"Connection open failed: {err}")
        self._reconnect_delay = min(self._reconnect_delay + 1, 30)
        self._stop_ioloop()

    def _on_connection_closed(self, connection: pika.SelectConnection, reason: Exception):
        """Called when connection is closed."""
        log.info(f"Connection closed: {reason}")
        self._channel = None
        self._consumer_tag = None
        self._consuming = False

        if self._closing:
            log.info("Connection closed cleanly (worker shutting down)")
            self._stop_ioloop()
        else:
            log.warning("Connection lost unexpectedly - will reconnect")
            self._should_reconnect = True
            self._stop_ioloop()

    def _open_channel(self):
        """Open a new channel."""
        log.info("Opening channel...")
        self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_channel_open(self, channel: pika.channel.Channel):
        """Called when channel is opened."""
        log.info("Channel opened")
        self._channel = channel
        self._setup_channel()

    def _on_channel_closed(self, channel: pika.channel.Channel, reason: Exception):
        """Called when channel is closed."""
        log.warning(f"Channel closed: {reason}")
        self._channel = None
        if self._closing:
            # Already shutting down; nothing more to do
            return
        # Unexpected channel close → schedule reconnect
        self._should_reconnect = True
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.close()
            except Exception as e:
                log.debug(f"Connection close error (expected if already closed): {e}")
                self._stop_ioloop()
        else:
            # Connection already closed; stop ioloop to trigger reconnect loop
            self._stop_ioloop()

    def _setup_channel(self):
        """Setup channel: declare exchange, queue, bindings."""
        if not self._channel:
            return

        # Declare exchange
        self._channel.exchange_declare(
            exchange=settings.rmq_queue_exchange,
            exchange_type="direct",
            durable=True,
            callback=functools.partial(self._on_exchange_declareok, exchange=settings.rmq_queue_exchange)
        )

    def _on_exchange_declareok(self, _unused_frame, exchange: str):
        """Called when exchange declaration succeeds."""
        log.info(f"Exchange declared: {exchange}")
        self._setup_queue()

    def _setup_queue(self):
        """Declare queue and bind to exchange."""
        self._channel.queue_declare(
            queue=settings.rmq_queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": settings.rmq_queue_dead_letter_exchange,
                "x-dead-letter-routing-key": settings.rmq_queue_routing_key_dead_letter,
            },
            callback=self._on_queue_declareok
        )

    def _on_queue_declareok(self, _unused_frame):
        """Called when queue declaration succeeds."""
        log.info(f"Queue declared: {settings.rmq_queue_name}")
        self._bind_queue()

    def _bind_queue(self):
        """Bind queue to exchange with routing key."""
        self._channel.queue_bind(
            queue=settings.rmq_queue_name,
            exchange=settings.rmq_queue_exchange,
            routing_key=settings.rmq_queue_routing_key,
            callback=self._on_bindok
        )

        # Also setup dead letter exchange/queue
        self._channel.exchange_declare(
            exchange=settings.rmq_queue_dead_letter_exchange,
            exchange_type="direct",
            durable=True,
            callback=functools.partial(self._on_dlx_exchange_declareok, exchange=settings.rmq_queue_dead_letter_exchange)
        )

    def _on_dlx_exchange_declareok(self, _unused_frame, exchange: str):
        """Called when DLX exchange declaration succeeds."""
        log.info(f"DLX exchange declared: {exchange}")
        self._channel.queue_declare(
            queue=settings.rmq_queue_dead_letter_name,
            durable=True,
            callback=self._on_dlx_queue_declareok
        )

    def _on_dlx_queue_declareok(self, _unused_frame):
        """Called when DLX queue declaration succeeds."""
        log.info(f"DLX queue declared: {settings.rmq_queue_dead_letter_name}")
        self._channel.queue_bind(
            queue=settings.rmq_queue_dead_letter_name,
            exchange=settings.rmq_queue_dead_letter_exchange,
            routing_key=settings.rmq_queue_routing_key_dead_letter,
            callback=lambda _: log.info("DLQ bound")
        )
        # After DLQ setup, continue with main queue binding continuation
        # The main queue bind already happened, so we're ready for QoS
        self._set_qos()

    def _on_bindok(self, _unused_frame):
        """Called when queue binding succeeds."""
        log.info("Queue bound")
        self._set_qos()

    def _set_qos(self):
        """Set prefetch count."""
        if not self._channel:
            return
        self._channel.basic_qos(
            prefetch_count=getattr(settings, 'worker_prefetch_count', 1),
            callback=self._on_basic_qos_ok
        )

    def _on_basic_qos_ok(self, _unused_frame):
        """Called when QoS is set."""
        log.info(f"QoS set to {getattr(settings, 'worker_prefetch_count', 1)}")
        self._start_consuming()

    def _start_consuming(self):
        """Start consuming messages."""
        log.info("Starting to consume")
        self._channel.add_on_close_callback(self._on_channel_closed)
        self._channel.add_on_cancel_callback(self._on_consumer_cancelled)

        self._consumer_tag = self._channel.basic_consume(
            queue=settings.rmq_queue_name,
            on_message_callback=self._on_message_wrapper
        )
        self._consuming = True
        log.info(f"Consumer started with tag: {self._consumer_tag}")

    def _on_consumer_cancelled(self, method_frame):
        """Called when consumer is cancelled by broker."""
        log.info(f"Consumer cancelled: {method_frame}")
        self._consuming = False
        if self._channel:
            self._channel.close()

    def _on_message_wrapper(
        self,
        channel: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes
    ):
        """Wrapper for message handling - submits to thread pool."""
        log.info(f"Received message, submitting to thread pool...")
        if self.executor:
            self.executor.submit(
                self._process_message_thread,
                channel,
                method,
                properties,
                body
            )
        else:
            log.error("Thread pool executor not initialized!")

    def _process_message_thread(
        self,
        channel: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes
    ):
        """Process message in thread pool. Ack/nack are scheduled on IOLoop thread."""
        try:
            self.message_handler.on_message(channel, method, properties, body)
            # Success: schedule ack on IOLoop thread
            if self._connection and not self._connection.is_closed:
                self._connection.ioloop.add_callback_threadsafe(
                    functools.partial(channel.basic_ack, method.delivery_tag)
                )
        except Exception as e:
            log.error(f"Error processing message: {e}")
            import traceback
            log.error(traceback.format_exc())
            # Failure: schedule nack on IOLoop thread (requeue=False)
            if channel.is_open and self._connection and not self._connection.is_closed:
                self._connection.ioloop.add_callback_threadsafe(
                    functools.partial(channel.basic_nack, method.delivery_tag, False)
                )

    def stop(self):
        """Cleanly shutdown the consumer."""
        if self._stopping:
            return

        log.info("Stopping consumer...")
        self._stopping = True
        self._closing = True  # Always set closing flag to prevent reconnection

        if self._channel and self._consuming:
            self._stop_consuming()
        else:
            # Not consuming; close connection directly
            if self._connection and not self._connection.is_closing and not self._connection.is_closed:
                try:
                    self._connection.close()
                except Exception as e:
                    log.debug(f"Connection close during shutdown: {e}")
                    self._stop_ioloop()

    def _stop_consuming(self):
        """Cancel the consumer and wait for confirmation."""
        if not self._channel or not self._consuming:
            return

        log.info("Sending Basic.Cancel")
        self._channel.basic_cancel(
            consumer_tag=self._consumer_tag,
            callback=self._on_cancelok
        )

    def _on_cancelok(self, _unused_frame):
        """Called when broker acknowledges cancel."""
        log.info("Consumer cancelled successfully")
        self._consuming = False
        self._close_channel()

    def _close_channel(self):
        """Close the channel cleanly."""
        if self._channel:
            log.info("Closing channel")
            self._channel.close()
            self._channel = None

    def _stop_ioloop(self):
        """Stop the IOLoop if it's running. Idempotent."""
        if self._connection and not self._connection.is_closed:
            try:
                # This will cause ioloop.start() to return
                self._connection.ioloop.stop()
            except Exception:
                # Already stopped or invalid state; safe to ignore
                pass

    def shutdown(self):
        """Shutdown worker gracefully."""
        log.info("Shutting down worker...")

        self.stop()

        # Wait for IOLoop to stop
        if self._connection:
            while not self._connection.is_closed and not self._closing:
                time.sleep(0.1)

        if self.executor:
            self.executor.shutdown(wait=True)
            log.info("Thread pool executor shutdown complete")

        # Only shutdown analysis_executor if we created it
        if self.analysis_executor and hasattr(self, '_created_executor') and self._created_executor:
            self.analysis_executor.shutdown(wait=True)
            log.info("Process pool executor shutdown complete")

        log.info("Worker shutdown complete")

    def _get_reconnect_delay(self) -> int:
        """Calculate reconnect delay with exponential backoff."""
        if self._should_reconnect:
            self._reconnect_delay = min(self._reconnect_delay + 1, 30)
        return self._reconnect_delay
